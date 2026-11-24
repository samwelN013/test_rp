import re
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


def create_resilient_session(
    retries: int = 5, backoff_factor: float = 2.0
) -> requests.Session:
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

    Uses `fromId` when resuming from a known trade ID to prevent gaps or duplicates,
    and `startTime` pagination when starting a fresh time window.
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
                    tqdm.write(
                        f"❌ REST API error ({res.status_code}): {res.text}"
                    )
                    break

                data = res.json()
                if not data:
                    break

                filtered_batch = [t for t in data if t["T"] <= end_ts]
                all_trades.extend(filtered_batch)

                if data[-1]["T"] >= end_ts:
                    break

                next_from_id = data[-1]["a"] + 1

                progress_pct = min(
                    int(((data[-1]["T"] - start_ts) / total_span_ms) * 100), 99
                )
                if progress_pct > last_pct:
                    pbar.update(progress_pct - last_pct)
                    last_pct = progress_pct

                time.sleep(0.08)

            except Exception as e:
                tqdm.write(
                    f"⚠️ Network glitch during API fetch ({e}). Retrying..."
                )
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

    df = df.drop_duplicates(subset=["agg_trade_id"], keep="last")
    return df[COLUMN_NAMES]


def inspect_parquet_coverage(
    pqt_path: Path,
) -> tuple[int | None, int | None, int]:
    """Reads max(transact_time), max(agg_trade_id), and row count from a Parquet file."""
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
        return None, None, 0


def is_day_file_complete(pqt_path: Path, date_str: str) -> bool:
    """Verifies whether a historical daily Parquet file covers up to the end of that UTC day."""
    max_ts, _, row_cnt = inspect_parquet_coverage(pqt_path)
    if max_ts is None or row_cnt == 0:
        return False

    day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    min_expected_end_ts = int(
        (day_start + timedelta(hours=23, minutes=55)).timestamp() * 1000
    )
    return max_ts >= min_expected_end_ts


def download_vision_zip_to_parquet(
    symbol: str, date_str: str, output_parquet_path: Path, tmp_path: Path
) -> bool:
    """Attempts to download and convert a full day's zip from Binance Vision. Returns True on success."""
    file_name = f"{symbol}-aggTrades-{date_str}"
    zip_filename = f"{file_name}.zip"
    pqt_str = output_parquet_path.as_posix()
    url = f"https://data.binance.vision/data/futures/um/daily/aggTrades/{symbol}/{zip_filename}"

    try:
        res = SESSION.get(url, stream=True, timeout=20)
    except Exception:
        return False

    if not res or res.status_code != 200:
        return False

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
            if not csv_members:
                return False

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
        return True
    except Exception as e:
        tqdm.write(f"⚠️ Zip extraction error for {date_str}: {e}")
        temp_zip_file.unlink(missing_ok=True)
        return False


def consolidate_yesterday_hourly_files(
    symbol: str,
    yesterday_str: str,
    pqt_folder: Path,
    tmp_path: Path,
):
    """Handles rollover of yesterday's hourly Parquet files (`_H00`..`_H23`):
    - If all 24 hours exist, merges them directly into `{symbol}-aggTrades-{yesterday}.parquet`.
    - If < 24 hours exist, tries Binance Vision first; otherwise tops up the missing hours via REST API
      and merges everything into the daily file.
    - Deletes yesterday's hourly shards once the daily file is safely written.
    """
    hourly_files = sorted(
        pqt_folder.glob(f"{symbol}-aggTrades-{yesterday_str}_H*.parquet")
    )
    if not hourly_files:
        return

    daily_target = pqt_folder / f"{symbol}-aggTrades-{yesterday_str}.parquet"
    daily_pqt_str = daily_target.as_posix()

    # If the full daily file already exists and is complete, simply clean up leftover hourly shards
    if daily_target.exists() and is_day_file_complete(
        daily_target, yesterday_str
    ):
        for hf in hourly_files:
            hf.unlink(missing_ok=True)
        print(
            f"🧹 Cleaned up {len(hourly_files)} redundant hourly shards for {yesterday_str}."
        )
        return

    # Map existing valid hour indices (0..23)
    existing_hours: dict[int, Path] = {}
    for hf in hourly_files:
        match = re.search(r"_H(\d{2})\.parquet$", hf.name)
        if match:
            hr = int(match.group(1))
            if 0 <= hr <= 23:
                existing_hours[hr] = hf

    print(
        f"🔄 Rolling over {len(existing_hours)}/24 hourly shard(s) from {yesterday_str} into daily Parquet..."
    )

    # Case 1: All 24 hours are already on disk -> merge directly via DuckDB
    if len(existing_hours) == 24:
        shard_paths = [existing_hours[h].as_posix() for h in range(24)]
        duckdb.sql(
            f"""
            COPY (
                SELECT DISTINCT ON (agg_trade_id) *
                FROM read_parquet({shard_paths})
                ORDER BY agg_trade_id
            )
            TO '{daily_pqt_str}'
            (FORMAT 'parquet', COMPRESSION 'zstd');
            """
        )
        for hf in hourly_files:
            hf.unlink(missing_ok=True)
        print(
            f"✅ Merged 24/24 hourly files into {daily_target.name} and removed hourly shards."
        )
        return

    # Case 2: Fewer than 24 hours on disk -> check if Binance Vision zip is already available
    if download_vision_zip_to_parquet(
        symbol, yesterday_str, daily_target, tmp_path
    ):
        for hf in hourly_files:
            hf.unlink(missing_ok=True)
        print(
            f"✅ Replaced partial hourly shards with full Binance Vision file: {daily_target.name}"
        )
        return

    # Case 3: Vision zip not ready yet -> top up missing hours via REST API and merge
    day_start = datetime.strptime(yesterday_str, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    day_end_ts = int((day_start + timedelta(days=1)).timestamp() * 1000) - 1

    # Inspect the latest contiguous hourly shard we have
    sorted_hrs = sorted(existing_hours.keys())
    contiguous_hrs = []
    for idx, h in enumerate(sorted_hrs):
        if h == idx:
            contiguous_hrs.append(h)
        else:
            break

    if contiguous_hrs:
        last_hr = contiguous_hrs[-1]
        last_shard = existing_hours[last_hr]
        max_ts, max_id, _ = inspect_parquet_coverage(last_shard)
        resume_start_ts = (
            max_ts
            if max_ts
            else int(
                (day_start + timedelta(hours=last_hr + 1)).timestamp() * 1000
            )
        )
        shard_paths = [
            existing_hours[h].as_posix() for h in contiguous_hrs
        ]
        existing_df = duckdb.sql(
            f"SELECT * FROM read_parquet({shard_paths})"
        ).df()
    else:
        max_id = None
        resume_start_ts = int(day_start.timestamp() * 1000)
        existing_df = pd.DataFrame(columns=COLUMN_NAMES)

    print(
        f"🌐 Topping up remaining hours of {yesterday_str} via REST API to 23:59:59 UTC..."
    )
    missing_df = fetch_aggtrades_range(
        symbol,
        start_ts=resume_start_ts,
        end_ts=day_end_ts,
        last_known_id=max_id,
    )

    combined_df = pd.concat(
        [existing_df, missing_df], ignore_index=True
    ).drop_duplicates(subset=["agg_trade_id"], keep="last")

    if not combined_df.empty:
        duckdb.sql(
            f"COPY combined_df TO '{daily_pqt_str}' (FORMAT 'parquet', COMPRESSION 'zstd');"
        )
        for hf in hourly_files:
            hf.unlink(missing_ok=True)
        print(
            f"✅ Topped up and merged into {daily_target.name} ({len(combined_df):,} rows)."
        )
    else:
        print(f"❌ Failed to consolidate {yesterday_str}.")


def download_full_day_to_parquet(
    symbol: str, date_str: str, output_parquet_path: Path, tmp_path: Path
):
    """Downloads a full completed UTC day (Binance Vision Zip first, REST API fallback)."""
    pqt_str = output_parquet_path.as_posix()

    if download_vision_zip_to_parquet(
        symbol, date_str, output_parquet_path, tmp_path
    ):
        tqdm.write(
            f"✅ Downloaded full day (Vision): {output_parquet_path.name}"
        )
        return

    day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    day_start_ts = int(day_start.timestamp() * 1000)
    day_end_ts = int((day_start + timedelta(days=1)).timestamp() * 1000) - 1

    tqdm.write(
        f"⚠️ Vision archive for {date_str} unavailable. Fetching full day via REST API..."
    )
    df = fetch_aggtrades_range(
        symbol, start_ts=day_start_ts, end_ts=day_end_ts
    )
    if not df.empty:
        duckdb.sql(
            f"COPY df TO '{pqt_str}' (FORMAT 'parquet', COMPRESSION 'zstd');"
        )
        tqdm.write(f"✅ Saved full day via API: {output_parquet_path.name}")
    else:
        tqdm.write(f"❌ Failed to fetch data for {date_str}.")


def update_today_hourly_files(
    symbol: str, today_str: str, pqt_folder: Path, now_utc: datetime
):
    """Creates one immutable Parquet file per completed UTC hour for the current day:
    `{symbol}-aggTrades-{YYYY-MM-DD}_H{00..23}.parquet`.
    """
    completed_hours_count = now_utc.hour  # e.g., at 19:20 UTC, hours 00..18 (19 hours) are finished

    if completed_hours_count == 0:
        print(
            f"⏳ Current UTC time is {now_utc.strftime('%H:%M')} — first hour (H00) not finished yet."
        )
        return

    day_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    missing_hours = []

    for h in range(completed_hours_count):
        hr_file = pqt_folder / f"{symbol}-aggTrades-{today_str}_H{h:02d}.parquet"
        if not hr_file.exists():
            missing_hours.append(h)

    if not missing_hours:
        print(
            f"✅ All {completed_hours_count} closed hour file(s) (H00–H{completed_hours_count - 1:02d}) "
            f"for {today_str} are up to date."
        )
        return

    print(
        f"🌐 Fetching {len(missing_hours)} missing closed hour(s) for {today_str}: "
        f"{[f'H{h:02d}' for h in missing_hours]}"
    )

    pbar = tqdm(missing_hours, desc=f"Hourly {symbol}", unit="hr")
    for h in pbar:
        hr_filename = f"{symbol}-aggTrades-{today_str}_H{h:02d}.parquet"
        hr_path = pqt_folder / hr_filename
        pqt_str = hr_path.as_posix()
        pbar.set_postfix_str(f"H{h:02d}")

        hr_start_ts = int((day_start + timedelta(hours=h)).timestamp() * 1000)
        hr_end_ts = (
            int((day_start + timedelta(hours=h + 1)).timestamp() * 1000) - 1
        )

        # If the immediately preceding hour file exists, grab its max_id for seamless pagination
        last_id = None
        if h > 0:
            prev_hr_path = (
                pqt_folder
                / f"{symbol}-aggTrades-{today_str}_H{h - 1:02d}.parquet"
            )
            _, prev_max_id, _ = inspect_parquet_coverage(prev_hr_path)
            if prev_max_id is not None:
                last_id = prev_max_id

        df = fetch_aggtrades_range(
            symbol,
            start_ts=hr_start_ts,
            end_ts=hr_end_ts,
            last_known_id=last_id,
        )

        if not df.empty:
            duckdb.sql(
                f"COPY df TO '{pqt_str}' (FORMAT 'parquet', COMPRESSION 'zstd');"
            )
            tqdm.write(
                f"✅ Saved {hr_filename} ({len(df):,} trades | {h:02d}:00–{h:02d}:59 UTC)"
            )
        else:
            tqdm.write(
                f"⚠️ No trades returned for {hr_filename} ({h:02d}:00–{h:02d}:59 UTC)."
            )


def download_and_convert(symbol: str = "SOLUSDT", prev_days: int = 30):
    """Maintains a Unified Master Folder containing:
      1. `prev_days` completed daily Parquet files (`{symbol}-aggTrades-YYYY-MM-DD.parquet`).
      2. Individual hourly Parquet files (`{symbol}-aggTrades-YYYY-MM-DD_H00..H23.parquet`)
         for every finished UTC hour of the current day.
    """
    symbol = symbol.upper()

    base_dir = (
        Path(__file__).resolve().parent.parent
        / "WYNAN"
        / "binance_aggts_hist"
    )
    pqt_folder = base_dir / f"{symbol}_current_data"
    pqt_folder.mkdir(parents=True, exist_ok=True)

    now_utc = datetime.now(timezone.utc)
    today_utc = now_utc.date()
    today_str = today_utc.strftime("%Y-%m-%d")
    yesterday_str = (today_utc - timedelta(days=1)).strftime("%Y-%m-%d")

    # Historical completed dates: [today - prev_days, yesterday]
    start_date = today_utc - timedelta(days=prev_days)
    completed_dates = [
        (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(prev_days)
    ]

    # Build exact set of allowed filenames in the folder
    valid_daily_filenames = {
        f"{symbol}-aggTrades-{d}.parquet" for d in completed_dates
    }
    valid_today_hourly_filenames = {
        f"{symbol}-aggTrades-{today_str}_H{h:02d}.parquet"
        for h in range(now_utc.hour)
    }
    # Temporarily retain yesterday's hourly shards until Step 1 consolidates them
    yesterday_hourly_prefix = f"{symbol}-aggTrades-{yesterday_str}_H"

    print("\n============================================================")
    print(f"=== Unified Master Pipeline: {symbol} ({prev_days}d + Hourly Shards) ===")
    print(f"Target Folder   : {pqt_folder.as_posix()}")
    print(f"Completed Window: {completed_dates[0]} to {completed_dates[-1]}")
    print(
        f"Today's Hours   : {today_str} (H00 to H{max(now_utc.hour - 1, 0):02d} UTC)"
    )
    print("============================================================")

    # 1. Prune out-of-window daily files & dead hourly shards from older days
    deleted_count = 0
    for file_path in pqt_folder.glob("*.parquet"):
        fname = file_path.name
        is_valid_daily = fname in valid_daily_filenames
        is_valid_today_hr = fname in valid_today_hourly_filenames
        is_yesterday_hr = fname.startswith(yesterday_hourly_prefix)

        if not (is_valid_daily or is_valid_today_hr or is_yesterday_hr):
            file_path.unlink()
            print(f"🗑️ Purged dead/out-of-window file: {fname}")
            deleted_count += 1

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 2. Roll over yesterday's hourly shards into yesterday's daily Parquet (if present)
        if prev_days >= 1:
            consolidate_yesterday_hourly_files(
                symbol, yesterday_str, pqt_folder, tmp_path
            )

        # 3. Verify all `prev_days` historical daily files exist and are complete
        dates_to_fetch = []
        for d_str in completed_dates:
            target_pqt = pqt_folder / f"{symbol}-aggTrades-{d_str}.parquet"
            if not target_pqt.exists():
                dates_to_fetch.append(d_str)
            elif not is_day_file_complete(target_pqt, d_str):
                print(
                    f"⚠️ Detected incomplete historical file: {target_pqt.name} — replacing it."
                )
                dates_to_fetch.append(d_str)

        if dates_to_fetch:
            print(f"\nProcessing {len(dates_to_fetch)} historical day(s)...")
            pbar = tqdm(
                dates_to_fetch, desc=f"Historical {symbol}", unit="day"
            )
            for d_str in pbar:
                pbar.set_postfix_str(d_str)
                target_pqt = pqt_folder / f"{symbol}-aggTrades-{d_str}.parquet"
                download_full_day_to_parquet(
                    symbol, d_str, target_pqt, tmp_path
                )
        else:
            print("✅ All historical daily files are complete and up to date.")

    # 4. Append any missing closed UTC hour Parquet files for today
    print()
    update_today_hourly_files(symbol, today_str, pqt_folder, now_utc)

    print(f"\n🎉 {symbol} Unified Master Folder is ready!\n")


if __name__ == "__main__":
    # download_and_convert(symbol="TAOUSDT", prev_days=30)
    # download_and_convert(symbol="BTCUSDT", prev_days=30)
    # download_and_convert(symbol="SOLUSDT", prev_days=2)
    # download_and_convert(symbol="ADAUSDT", prev_days=2)
    download_and_convert(symbol="XAUUSDT", prev_days=30)