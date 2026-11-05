import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import requests
from tqdm import tqdm

# ==========================================
# CONFIGURATION
# ==========================================
SYMBOL = "SOLUSDT"
START_MONTH = "10/2026"  # Format: MM/YYYY
END_MONTH = "11/2026"    # Format: MM/YYYY

# Folder setup
PQT_FOLDER = Path(__file__).resolve().parent.parent / "_inputs" / "pqt_folder"
PQT_FOLDER.mkdir(parents=True, exist_ok=True)


def generate_daily_list(start_str: str, end_str: str):
    """Generates all dates (YYYY-MM-DD) between start of start_month and end of end_month."""
    start_dt = datetime.strptime(start_str, "%m/%Y")
    
    # Calculate end date (last day of the end_month)
    end_month_dt = datetime.strptime(end_str, "%m/%Y")
    if end_month_dt.month == 12:
        next_month = datetime(end_month_dt.year + 1, 1, 1)
    else:
        next_month = datetime(end_month_dt.year, end_month_dt.month + 1, 1)
    end_dt = next_month - timedelta(days=1)

    dates = []
    current_dt = start_dt
    while current_dt <= end_dt:
        dates.append(current_dt.strftime("%Y-%m-%d"))
        current_dt += timedelta(days=1)

    return dates


def download_and_convert_bybit():
    days = generate_daily_list(START_MONTH, END_MONTH)
    total_start_time = time.time()

    print(f"Starting Bybit Futures download and conversion for {SYMBOL}...")
    print(f"Total days to process: {len(days)}\n")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Main progress bar for total days
        day_pbar = tqdm(days, desc="Overall Progress", unit="day")

        for date_str in day_pbar:
            # Bybit Futures trade format: SYMBOLYYYY-MM-DD.csv.gz
            gz_filename = f"{SYMBOL}{date_str}.csv.gz"
            output_parquet_path = PQT_FOLDER / f"{SYMBOL}-aggTrades-{date_str}.parquet"

            # Skip downloading if parquet already exists locally
            if output_parquet_path.exists():
                tqdm.write(f"⏭️  Already converted: {output_parquet_path.name}")
                continue

            # Bybit public data URL for derivatives trading history
            url = f"https://public.bybit.com/trading/{SYMBOL}/{gz_filename}"

            day_pbar.set_postfix_str(f"Fetching {gz_filename}")

            response = requests.get(url, stream=True)

            if response.status_code == 404:
                tqdm.write(f"⚠️  File not found on Bybit (404): {gz_filename}")
                continue
            elif response.status_code != 200:
                tqdm.write(f"❌ Failed to download {gz_filename} (Status: {response.status_code})")
                continue

            total_size = int(response.headers.get("content-length", 0))
            temp_gz_file = tmp_path / gz_filename

            # Stream download to temp directory
            with open(temp_gz_file, "wb") as f, tqdm(
                desc=f"Downloading {gz_filename}",
                total=total_size,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
                leave=False,
            ) as dl_pbar:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        dl_pbar.update(len(chunk))

            day_pbar.set_postfix_str(f"Converting to Parquet...")

            # DuckDB decompresses and parses .csv.gz natively on the fly
            gz_str = temp_gz_file.as_posix()
            pqt_str = output_parquet_path.as_posix()

            query = f"""
                COPY (SELECT * FROM read_csv_auto('{gz_str}'))
                TO '{pqt_str}'
                (FORMAT 'parquet', COMPRESSION 'zstd');
            """
            duckdb.sql(query)

            # Cleanup temp file
            temp_gz_file.unlink(missing_ok=True)

            tqdm.write(f"✅ Converted and saved: {output_parquet_path.name}")

    total_time = time.time() - total_start_time
    print(f"\nFinished! Total execution time: {total_time:.2f} seconds across {len(days)} day(s).")


if __name__ == "__main__":
    download_and_convert_bybit()