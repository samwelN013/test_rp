import tempfile
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from tqdm import tqdm

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


def create_resilient_session(retries=5, backoff_factor=2) -> requests.Session:
    """Creates a requests session configured with automatic retry logic and backoff.

    Handles DNS failures, connection drops, and HTTP rate limits (429/5xx).
    """
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


# Persistent network session with auto-retry
SESSION = create_resilient_session()


def fetch_day_via_rest_api(symbol: str, target_date: str) -> pd.DataFrame:
    """Fallback fetch for yesterday's data using Binance UM Futures REST API

    when data.binance.vision hasn't uploaded the daily archive yet.
    """
    dt_start = datetime.strptime(target_date, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    start_ts = int(dt_start.timestamp() * 1000)
    end_ts = int((dt_start + timedelta(days=1)).timestamp() * 1000) - 1

    url = "https://fapi.binance.com/fapi/v1/aggTrades"
    all_trades = []
    current_start = start_ts

    print(
        f"🌐 Fetching {target_date} via Binance REST API (Zip archive pending)..."
    )

    while current_start < end_ts:
        params = {
            "symbol": symbol.upper(),
            "startTime": current_start,
            "endTime": end_ts,
            "limit": 1000,
        }
        try:
            res = SESSION.get(url, params=params, timeout=15)
            if res.status_code != 200:
                print(f"❌ REST API error ({res.status_code}): {res.text}")
                break

            data = res.json()
            if not data:
                break

            all_trades.extend(data)
            last_time = data[-1]["T"]
            if last_time == current_start:
                current_start += 1
            else:
                current_start = last_time + 1
        except Exception as e:
            print(f"⚠️ Network glitch during REST API fetch: {e}. Retrying chunk...")
            time.sleep(3)
            continue

    if not all_trades:
        return pd.DataFrame()

    df = pd.DataFrame(all_trades)

    df = df.rename(
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

    return df[COLUMN_NAMES]


def download_and_convert(symbol: str = "SOLUSDT", days: int = 30):
    """Downloads & maintains a rolling window of N daily Parquet files up to yesterday (UTC)."""
    symbol = symbol.upper()

    base_dir = (
        Path(__file__).resolve().parent.parent
        / "_9LIVE_MKT_ANALYSIS_tdg"
        / "_inputs"
        / "binance_aggts"
    )
    pqt_folder = base_dir / f"{symbol}_current_data"
    pqt_folder.mkdir(parents=True, exist_ok=True)

    today_utc = datetime.now(timezone.utc).date()
    start_date = today_utc - timedelta(days=days)

    required_dates = [
        (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(days)
    ]

    valid_filenames = {
        f"{symbol}-aggTrades-{d_str}.parquet" for d_str in required_dates
    }

    print(f"\n==================================================")
    print(f"=== Rolling Data Pipeline: {symbol} ({days} Days) ===")
    print(f"Target Directory: {pqt_folder.as_posix()}")
    print(f"Required Date Range: {required_dates[0]} to {required_dates[-1]}")
    print(f"==================================================")

    # 1. Cleanup phase
    all_existing_parquets = list(pqt_folder.glob("*.parquet"))
    deleted_count = 0

    for file_path in all_existing_parquets:
        if file_path.name not in valid_filenames:
            file_path.unlink()
            print(f"🗑️ Deleted invalid/out-of-range file: {file_path.name}")
            deleted_count += 1

    if deleted_count > 0:
        print(f"Purged {deleted_count} unwanted parquet file(s).")

    # 2. Identify missing dates
    missing_dates = []
    for d_str in required_dates:
        target_pqt = pqt_folder / f"{symbol}-aggTrades-{d_str}.parquet"
        if not target_pqt.exists():
            missing_dates.append(d_str)

    if not missing_dates:
        print("✅ All data is up to date! No downloads required.\n")
        return

    print(f"Found {len(missing_dates)} missing day(s) to process.\n")

    # 3. Fetch missing files with retry & fallback safety
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        pbar = tqdm(missing_dates, desc=f"Processing {symbol}", unit="day")

        for date_str in pbar:
            file_name = f"{symbol}-aggTrades-{date_str}"
            zip_filename = f"{file_name}.zip"
            output_parquet_path = pqt_folder / f"{file_name}.parquet"
            pqt_str = output_parquet_path.as_posix()

            url = f"https://data.binance.vision/data/futures/um/daily/aggTrades/{symbol}/{zip_filename}"
            pbar.set_postfix_str(f"Fetching {zip_filename}")

            try:
                res = SESSION.get(url, stream=True, timeout=20)
            except Exception as e:
                tqdm.write(
                    f"⚠️ Network error connecting to Binance Vision ({e}). Swapping to REST API..."
                )
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
                        csv_members = [
                            n for n in z.namelist() if n.endswith(".csv")
                        ]
                        if csv_members:
                            extracted_csv_path = Path(
                                z.extract(csv_members[0], tmp_path)
                            )
                            csv_str = extracted_csv_path.as_posix()

                            query = f"""
                                COPY (SELECT * FROM read_csv_auto('{csv_str}'))
                                TO '{pqt_str}'
                                (FORMAT 'parquet', COMPRESSION 'zstd');
                            """
                            duckdb.sql(query)
                            extracted_csv_path.unlink(missing_ok=True)

                    temp_zip_file.unlink(missing_ok=True)
                    tqdm.write(
                        f"✅ Downloaded & Converted: {output_parquet_path.name}"
                    )
                except Exception as e:
                    tqdm.write(f"⚠️ Error processing zip file ({e}). Trying REST API fallback...")
                    df = fetch_day_via_rest_api(symbol, date_str)
                    if not df.empty:
                        query = f"COPY df TO '{pqt_str}' (FORMAT 'parquet', COMPRESSION 'zstd');"
                        duckdb.sql(query)
                        tqdm.write(f"✅ Generated via API & Saved: {output_parquet_path.name}")

            else:
                tqdm.write(
                    f"⚠️ Vision archive for {date_str} unavailable or dropped. Fallback to REST API..."
                )
                df = fetch_day_via_rest_api(symbol, date_str)

                if not df.empty:
                    query = f"COPY df TO '{pqt_str}' (FORMAT 'parquet', COMPRESSION 'zstd');"
                    duckdb.sql(query)
                    tqdm.write(
                        f"✅ Generated via API & Saved: {output_parquet_path.name}"
                    )
                else:
                    tqdm.write(
                        f"❌ Failed to fetch data for {date_str} via both Vision and REST API."
                    )

    print(
        f"\n🎉 Finished updating {symbol}! Window of {days} days is ready in '{pqt_folder.name}'.\n"
    )


if __name__ == "__main__":   
    download_and_convert(symbol="ADAUSDT", days=30) #1
    download_and_convert(symbol="ARBUSDT", days=30) #2
    download_and_convert(symbol="BNBUSDT", days=30) #3
    download_and_convert(symbol="BTCUSDT", days=30) #4
    download_and_convert(symbol="DOGEUSDT", days=30) #5
    download_and_convert(symbol="ETHUSDT", days=30) #6
    download_and_convert(symbol="HYPEUSDT", days=30) #7
    download_and_convert(symbol="SOLUSDT", days=30) #8
    download_and_convert(symbol="SUIUSDT", days=30) #9
    download_and_convert(symbol="TAOUSDT", days=30) #10
    download_and_convert(symbol="UNIUSDT", days=30) #11
    download_and_convert(symbol="WLDUSDT", days=30) #12
    download_and_convert(symbol="XRPUSDT", days=30) #13