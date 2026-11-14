import tempfile
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util import Retry

# Standard Binance UM Futures aggTrades Schema
COLUMN_NAMES = [
    "agg_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "transact_time",
    "is_buyer_maker",
]


def create_resilient_session(retries: int = 5, backoff_factor: float = 2.0) -> requests.Session:
    """Creates a requests session with automatic retry logic and exponential backoff."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = create_resilient_session()


def fetch_aggtrades_range(
    symbol: str,
    start_ts: int,
    end_ts: int,
    last_known_id: int | None = None,
) -> pd.DataFrame:
    """Fetches UM Futures aggTrades between [start_ts, end_ts] inclusive via REST API.

    Uses `fromId` when resuming from an existing file to guarantee zero gaps or duplicates,
    and `startTime` pagination when starting fresh.
    """
    url = "https://fapi.binance.com/fapi/v1/aggTrades"
    all_trades = []
    current_start = start_ts
    next_from_id = (last_known_id + 1) if last_known_id is not None else None

    total_span_ms = max(end_ts - start_ts, 1)

    with tqdm(
        desc=f"API Stream ({symbol})",
        total=100,
        unit="%",
        leave=False,
    ) as pbar:
        last_pct = 0

        while True:
            if next_from_id is not None:
                # Pagination by agg_trade_id (cannot combine fromId with startTime/endTime on Binance)
                params = {
                    "symbol": symbol.upper(),
                    "fromId": next_from_id,
                    "limit": 1000,
                }
            else:
                if current_start > end_ts:
                    break
                params = {
                    "symbol": symbol.upper(),
                    "startTime": current_start,
                    "endTime": end_ts,
                    "limit": 1000,
                }

            try:
                res = SESSION.get(url, params=params, timeout=15)
                if res.status_code == 429:
                    retry_after = int(res.headers.get("Retry-After", 5))
                    time.sleep(retry_after)
                    continue
                if res.status_code != 200:
                    tqdm.write(f"❌ REST API error ({res.status_code}): {res.text}")
                    break

                data = res.json()
                if not data:
                    break

                # Filter out any trades past our target end_ts (needed when paginating via fromId)
                filtered_batch = [t for t in data if t["T"] <= end_ts]
                all_trades.extend(filtered_batch)

                # Stop if we hit or passed end_ts
                if data[-1]["T"] >= end_ts:
                    break

                # Switch to exact ID-based pagination after the first batch so dense ms ticks never duplicate
                next_from_id = data[-1]["a"] + 1

                # Update progress bar based on timestamp progression
                progress_pct = min(
                    int(((data[-1]["T"] - start_ts) / total_span_ms) * 100), 99
                )
                if progress_pct > last_pct:
                    pbar.update(progress_pct - last_pct)
                    last_pct = progress_pct

                # Small courtesy pause to stay well below 2400 weight/min IP limit
                time.sleep(0.08)

            except Exception as e:
                tqdm.write(f"⚠️ Network glitch during API fetch ({e}). Retrying...")
                time.sleep(3)
                continue

        if last_pct < 100:
            pbar.update(100 - last_pct)

    if not all_trades:
        return pd.DataFrame(columns=COLUMN_NAMES)

    df = pd.DataFrame(all_trades).rename(
        columns={
            "a": "agg_trade_id",
            "p": "price",
            "q": "quantity",
            "f": "first_trade_id",
            "l": "last_trade_id",
            "T": "transact_time",
            "m": "is_buyer_maker",
        }
    )

    df["agg_trade_id"] = df["agg_trade_id"].astype("int64")
    df["price"] = df["price"].astype("float64")
    df["quantity"] = df["quantity"].astype("float64")
    df["first_trade_id"] = df["first_trade_id"].astype("int64")
    df["last_trade_id"] = df["last_trade_id"].astype("int64")
    df["transact_time"] = df["transact_time"].astype("int64")
    df["is_buyer_maker"] = df["is_buyer_maker"].astype("bool")

    # Deduplicate on agg_trade_id just in case
    df = df.drop_duplicates(subset=["agg_trade_id"], keep="last")
    return df[COLUMN_NAMES]


def inspect_parquet_coverage(pqt_path: Path) -> tuple[int | None, int | None, int]:
    """Reads max(transact_time), max(agg_trade_id), and row count from an existing Parquet file."""
    if not pqt_path.exists():
        return None, None, 0

    try:
        res = duckdb.sql(
            f"""
            SELECT 
                MAX(transact_time) AS max_ts,
                MAX(agg_trade_id) AS max_id,
                COUNT(*) AS row_cnt
            FROM read_parquet('{pqt_path.as_posix()}')
            """
        ).fetchone()
        return res[0], res[1], res[2]
    except Exception:
        # Corrupted or empty parquet file
        return None, None, 0


def is_day_file_complete(pqt_path: Path, date_str: str) -> bool:
    """Verifies whether a historical day's Parquet file covers up to the end of that UTC day."""
    max_ts, _, row_cnt = inspect_parquet_coverage(pqt_path)
    if max_ts is None or row_cnt == 0:
        return False

    day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    # Require trades reaching at least 23:55 UTC of that day (covers quiet pairs while catching partial intraday files)
    min_expected_end_ts = int((day_start + timedelta(hours=23, minutes=55)).timestamp() * 1000)
    return max_ts >= min_expected_end_ts


def download_full_day_to_parquet(symbol: str, date_str: str, output_parquet_path: Path, tmp_path: Path):
    """Downloads a full completed UTC day (Binance Vision Zip first, REST API fallback)."""
    file_name = f"{symbol}-aggTrades-{date_str}"
    zip_filename = f"{file_name}.zip"
    pqt_str = output_parquet_path.as_posix()
    url = f"https://data.binance.vision/data/futures/um/daily/aggTrades/{symbol}/{zip_filename}"

    try:
        res = SESSION.get(url, stream=True, timeout=20)
    except Exception:
        res = None

    if res and res.status_code == 200:
        total_size = int(res.headers.get("content-length", 0))
        temp_zip_file = tmp_path / zip_filename

        try:
            with open(temp_zip_file, "wb") as f, tqdm(
                desc=f"Downloading {zip_filename}",
                total=total_size,
                unit="iB",
                unit_scale=True,
                leave=False,
            ) as dl_pbar:
                for chunk in res.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        dl_pbar.update(len(chunk))

            with zipfile.ZipFile(temp_zip_file, "r") as z:
                csv_members = [n for n in z.namelist() if n.endswith(".csv")]
                if csv_members:
                    extracted_csv_path = Path(z.extract(csv_members[0], tmp_path))
                    csv_str = extracted_csv_path.as_posix()

                    duckdb.sql(
                        f"""
                        COPY (SELECT * FROM read_csv_auto('{csv_str}'))
                        TO '{pqt_str}'
                        (FORMAT 'parquet', COMPRESSION 'zstd');
                        """
                    )
                    extracted_csv_path.unlink(missing_ok=True)

            temp_zip_file.unlink(missing_ok=True)
            tqdm.write(f"✅ Downloaded full day (Vision): {output_parquet_path.name}")
            return
        except Exception as e:
            tqdm.write(f"⚠️ Zip error for {date_str} ({e}), falling back to REST API...")
            temp_zip_file.unlink(missing_ok=True)

    # REST API Fallback (or top-up if a partial file from yesterday already exists)
    day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    day_start_ts = int(day_start.timestamp() * 1000)
    day_end_ts = int((day_start + timedelta(days=1)).timestamp() * 1000) - 1

    existing_max_ts, existing_max_id, existing_rows = inspect_parquet_coverage(output_parquet_path)

    if existing_max_ts and existing_rows > 0 and existing_max_ts >= day_start_ts:
        tqdm.write(f"🔄 Topping up incomplete file for {date_str} to 23:59:59 UTC...")
        new_df = fetch_aggtrades_range(
            symbol,
            start_ts=existing_max_ts,
            end_ts=day_end_ts,
            last_known_id=existing_max_id,
        )
        if not new_df.empty:
            old_df = duckdb.sql(f"SELECT * FROM read_parquet('{pqt_str}')").df()
            combined_df = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates(
                subset=["agg_trade_id"], keep="last"
            )
            duckdb.sql(f"COPY combined_df TO '{pqt_str}' (FORMAT 'parquet', COMPRESSION 'zstd');")
            tqdm.write(f"✅ Completed full day via API top-up: {output_parquet_path.name}")
        else:
            tqdm.write(f"✅ Verified complete day: {output_parquet_path.name}")
    else:
        tqdm.write(f"🌐 Fetching full day {date_str} via REST API...")
        df = fetch_aggtrades_range(symbol, start_ts=day_start_ts, end_ts=day_end_ts)
        if not df.empty:
            duckdb.sql(f"COPY df TO '{pqt_str}' (FORMAT 'parquet', COMPRESSION 'zstd');")
            tqdm.write(f"✅ Saved full day via API: {output_parquet_path.name}")
        else:
            tqdm.write(f"❌ Failed to fetch data for {date_str}.")


def update_intraday_file(symbol: str, today_str: str, today_pqt_path: Path, now_utc: datetime):
    """Creates or incrementally appends closed UTC hours of the current day up to the last closed hour."""
    day_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    last_closed_hour_end = now_utc.replace(minute=0, second=0, microsecond=0) - timedelta(milliseconds=1)

    day_start_ts = int(day_start.timestamp() * 1000)
    target_end_ts = int(last_closed_hour_end.timestamp() * 1000)
    pqt_str = today_pqt_path.as_posix()

    if target_end_ts < day_start_ts:
        print(f"⏳ Current UTC time is {now_utc.strftime('%H:%M')} — first hour (00:00-01:00) not closed yet.")
        return

    closed_hour_label = (last_closed_hour_end + timedelta(milliseconds=1)).strftime("%H:%M UTC")
    existing_max_ts, existing_max_id, existing_rows = inspect_parquet_coverage(today_pqt_path)

    if existing_max_ts and existing_rows > 0:
        # Check if already updated up to the latest closed hour (allow 2-minute quiet-market buffer)
        if existing_max_ts >= (target_end_ts - 120_000):
            print(f"✅ Intraday file {today_pqt_path.name} is already up to date through {closed_hour_label}.")
            return

        last_saved_dt = datetime.fromtimestamp(existing_max_ts / 1000, tz=timezone.utc)
        print(
            f"🔄 Appending new hourly ticks to {today_pqt_path.name} "
            f"({last_saved_dt.strftime('%H:%M:%S')} -> {closed_hour_label})..."
        )
        new_df = fetch_aggtrades_range(
            symbol,
            start_ts=existing_max_ts,
            end_ts=target_end_ts,
            last_known_id=existing_max_id,
        )

        if not new_df.empty:
            old_df = duckdb.sql(f"SELECT * FROM read_parquet('{pqt_str}')").df()
            combined_df = pd.concat([old_df, new_df], ignore_index=True).drop_duplicates(
                subset=["agg_trade_id"], keep="last"
            )
            duckdb.sql(f"COPY combined_df TO '{pqt_str}' (FORMAT 'parquet', COMPRESSION 'zstd');")
            print(
                f"✅ Appended {len(new_df):,} new trades -> {today_pqt_path.name} "
                f"(Total: {len(combined_df):,} rows through {closed_hour_label})"
            )
        else:
            print(f"✅ No new trades found up to {closed_hour_label}.")
    else:
        print(f"🌐 Building intraday file {today_pqt_path.name} (00:00 UTC -> {closed_hour_label})...")
        df = fetch_aggtrades_range(symbol, start_ts=day_start_ts, end_ts=target_end_ts)
        if not df.empty:
            duckdb.sql(f"COPY df TO '{pqt_str}' (FORMAT 'parquet', COMPRESSION 'zstd');")
            print(
                f"✅ Created intraday file: {today_pqt_path.name} "
                f"({len(df):,} rows through {closed_hour_label})"
            )
        else:
            print(f"⚠️ No trades returned for {today_str} up to {closed_hour_label}.")


def download_and_convert(symbol: str = "SOLUSDT", prev_days: int = 30):
    """Maintains a Unified Master Folder containing:
      1. `prev_days` completed daily Parquet files (up to yesterday UTC).
      2. Today's incremental intraday Parquet file up to the last closed UTC hour.
    """
    symbol = symbol.upper()

    base_dir = (
        Path(__file__).resolve().parent.parent
        / "_9LIVE_MKT_ANALYSIS_tdg"
        / "_inputs"
        / "binance_aggts"
    )
    pqt_folder = base_dir / f"{symbol}_current_data"
    pqt_folder.mkdir(parents=True, exist_ok=True)

    now_utc = datetime.now(timezone.utc)
    today_utc = now_utc.date()
    today_str = today_utc.strftime("%Y-%m-%d")

    # Historical completed dates: [today - prev_days, yesterday]
    start_date = today_utc - timedelta(days=prev_days)
    completed_dates = [
        (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(prev_days)
    ]

    # Valid filenames in folder = `prev_days` historical files + today's intraday file
    valid_filenames = {f"{symbol}-aggTrades-{d}.parquet" for d in completed_dates}
    today_filename = f"{symbol}-aggTrades-{today_str}.parquet"
    valid_filenames.add(today_filename)

    print(f"\n============================================================")
    print(f"=== Unified Master Pipeline: {symbol} ({prev_days}d + Intraday) ===")
    print(f"Target Folder: {pqt_folder.as_posix()}")
    print(f"Completed Window: {completed_dates[0]} to {completed_dates[-1]}")
    print(f"Intraday Target : {today_filename} (up to last closed UTC hour)")
    print(f"============================================================")

    # 1. Strict Pruning: Remove any parquet file outside the rolling window
    deleted_count = 0
    for file_path in pqt_folder.glob("*.parquet"):
        if file_path.name not in valid_filenames:
            file_path.unlink()
            print(f"🗑️ Purged out-of-window file: {file_path.name}")
            deleted_count += 1

    # 2. Check completed days (detects both missing days AND incomplete yesterday rollover files)
    dates_to_fetch = []
    for d_str in completed_dates:
        target_pqt = pqt_folder / f"{symbol}-aggTrades-{d_str}.parquet"
        if not target_pqt.exists():
            dates_to_fetch.append(d_str)
        elif not is_day_file_complete(target_pqt, d_str):
            print(f"⚠️ Detected incomplete historical file: {target_pqt.name} — will complete it.")
            dates_to_fetch.append(d_str)

    if dates_to_fetch:
        print(f"\nProcessing {len(dates_to_fetch)} historical day(s)...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            pbar = tqdm(dates_to_fetch, desc=f"Historical {symbol}", unit="day")
            for d_str in pbar:
                pbar.set_postfix_str(d_str)
                target_pqt = pqt_folder / f"{symbol}-aggTrades-{d_str}.parquet"
                download_full_day_to_parquet(symbol, d_str, target_pqt, tmp_path)
    else:
        print("✅ All historical daily files are complete and up to date.")

    # 3. Update today's intraday file up to the last closed UTC hour
    print()
    today_pqt_path = pqt_folder / today_filename
    update_intraday_file(symbol, today_str, today_pqt_path, now_utc)

    print(f"\n🎉 {symbol} Unified Master Folder is ready!\n")


if __name__ == "__main__":
    download_and_convert(symbol="ADAUSDT", prev_days=33)

    # -------------------------------------
    # rolling_days = 33
    # # symbols = ["ADAUSDT", "WLDUSDT", "TAOUSDT", "HYPEUSDT"] # MAIN COINS

    # symbols = ["INJUSDT", "ARBUSDT", "UNIUSDT", "NEARUSDT",
    #            "ICPUSDT", "TIAUSDT"]  # VOLATILITY COINS
    
    # # symbols = ["SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT", "ETHUSDT", "BTCUSDT"] # CONTROL COINS

    # for coinpair in symbols:
    #     download_and_convert(symbol=coinpair, prev_days=rolling_days)
# --------------------------------------
