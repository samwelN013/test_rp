import tempfile
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pandas as pd
import requests
from tqdm import tqdm

# Folder setup
PQT_FOLDER = Path(__file__).resolve().parent.parent / "_inputs" / "pqt_folder"
PQT_FOLDER.mkdir(parents=True, exist_ok=True)

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
        res = requests.get(url, params=params)
        if res.status_code != 200:
            print(f"❌ REST API error ({res.status_code}): {res.text}")
            break

        data = res.json()
        if not data:
            break

        all_trades.extend(data)
        # Advance timestamp past last returned trade
        last_time = data[-1]["T"]
        if last_time == current_start:
            # Prevent infinite loops on dense timestamps
            current_start += 1
        else:
            current_start = last_time + 1

    if not all_trades:
        return pd.DataFrame()

    df = pd.DataFrame(all_trades)

    # Rename & align API output keys to match standard Binance CSV schema
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

    # Convert data types to match raw Binance CSV outputs
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
    # 1. Determine date boundaries in UTC
    today_utc = datetime.now(timezone.utc).date()
    yesterday = today_utc - timedelta(days=1)
    start_date = today_utc - timedelta(days=days)

    # List of required YYYY-MM-DD dates in range [start_date, yesterday]
    required_dates = [
        (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(days)
    ]

    print(
        f"=== Rolling Data Pipeline: {symbol} ({days} Days) ==="
    )
    print(f"Required Date Range: {required_dates[0]} to {required_dates[-1]}")

    # 2. Cleanup phase: Remove parquet files older than start_date
    existing_files = list(PQT_FOLDER.glob(f"{symbol}-aggTrades-*.parquet"))
    deleted_count = 0

    for file_path in existing_files:
        try:
            # Extract date string from format: SYMBOL-aggTrades-YYYY-MM-DD.parquet
            file_date_str = file_path.name.replace(
                f"{symbol}-aggTrades-", ""
            ).replace(".parquet", "")
            file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()

            if file_date < start_date or file_date > yesterday:
                file_path.unlink()
                print(f"🗑️ Deleted out-of-range file: {file_path.name}")
                deleted_count += 1
        except ValueError:
            # Skip files that don't match date formatting
            continue

    # 3. Check missing files
    missing_dates = []
    for d_str in required_dates:
        target_pqt = PQT_FOLDER / f"{symbol}-aggTrades-{d_str}.parquet"
        if not target_pqt.exists():
            missing_dates.append(d_str)

    if not missing_dates:
        print("\n✅ All data is up to date! No downloads required.")
        return

    print(f"\nFound {len(missing_dates)} missing day(s) to process.\n")

    # 4. Fetch missing files
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        pbar = tqdm(missing_dates, desc="Processing Days", unit="day")

        for date_str in pbar:
            file_name = f"{symbol}-aggTrades-{date_str}"
            zip_filename = f"{file_name}.zip"
            output_parquet_path = PQT_FOLDER / f"{file_name}.parquet"
            pqt_str = output_parquet_path.as_posix()

            # URL for Binance Daily Vision dumps
            url = f"https://data.binance.vision/data/futures/um/daily/aggTrades/{symbol}/{zip_filename}"
            pbar.set_postfix_str(f"Fetching {zip_filename}")

            res = requests.get(url, stream=True)

            if res.status_code == 200:
                # OPTION A: Download from Binance Vision Archive
                total_size = int(res.headers.get("content-length", 0))
                temp_zip_file = tmp_path / zip_filename

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

                # Extract CSV
                with zipfile.ZipFile(temp_zip_file, "r") as z:
                    csv_members = [
                        n for n in z.namelist() if n.endswith(".csv")
                    ]
                    if csv_members:
                        extracted_csv_path = Path(
                            z.extract(csv_members[0], tmp_path)
                        )
                        csv_str = extracted_csv_path.as_posix()

                        # Read CSV and dump to parquet
                        query = f"""
                            COPY (SELECT * FROM read_csv_auto('{csv_str}'))
                            TO '{pqt_str}'
                            (FORMAT 'parquet', COMPRESSION 'zstd');
                        """
                        duckdb.sql(query)
                        extracted_csv_path.unlink(missing_ok=True)

                temp_zip_file.unlink(missing_ok=True)
                tqdm.write(
                    f"✅ Downloaded & Converted: {output_parquet_path.name}")

            else:
                # OPTION B: Fallback to REST API (Instant Yesterday Retrieval)
                tqdm.write(
                    f"⚠️ Vision archive for {date_str} not ready. Fallback to REST API..."
                )
                df = fetch_day_via_rest_api(symbol, date_str)

                if not df.empty:
                    query = f"""
                        COPY df TO '{pqt_str}' (FORMAT 'parquet', COMPRESSION 'zstd');
                    """
                    duckdb.sql(query)
                    tqdm.write(
                        f"✅ Generated via API & Saved: {output_parquet_path.name}"
                    )
                else:
                    tqdm.write(
                        f"❌ Failed to fetch data for {date_str} via REST API."
                    )

    print(
        f"\n🎉 Pipeline Finished! Your rolling window of {days} days is ready in '{PQT_FOLDER.name}'."
    )


if __name__ == "__main__":
    # Call with parameters
    download_and_convert(symbol="SOLUSDT", days=4)
