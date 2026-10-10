import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

import duckdb
import requests
from tqdm import tqdm

# ==========================================
# CONFIGURATION
# ==========================================
SYMBOL = "SOLUSDT"
START_MONTH = "12/2025"  # Format: MM/YYYY
END_MONTH = "12/2025"  # Format: MM/YYYY

# Market type: 'um' (USD-M Futures) or 'cm' (COIN-M Futures)
MARKET_TYPE = "um"

# Folder setup
PQT_FOLDER = Path(__file__).resolve().parent.parent / "_inputs" / "pqt_folder"
PQT_FOLDER.mkdir(parents=True, exist_ok=True)


def generate_month_list(start_str: str, end_str: str):
    """Generates a list of YYYY-MM strings between start and end month inclusive."""
    start_dt = datetime.strptime(start_str, "%m/%Y")
    end_dt = datetime.strptime(end_str, "%m/%Y")

    months = []
    current_year = start_dt.year
    current_month = start_dt.month

    while (current_year, current_month) <= (end_dt.year, end_dt.month):
        months.append(f"{current_year}-{current_month:02d}")
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    return months


def download_and_convert():
    months = generate_month_list(START_MONTH, END_MONTH)
    total_start_time = time.time()

    print(
        f"Starting download and conversion for {SYMBOL} ({MARKET_TYPE.upper()} Futures)..."
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Main progress bar wrapping month batch
        month_pbar = tqdm(months, desc="Overall Progress", unit="file")

        for year_month in month_pbar:
            file_name = f"{SYMBOL}-aggTrades-{year_month}"
            zip_filename = f"{file_name}.zip"

            # Binance Data Vision URL
            url = f"https://data.binance.vision/data/futures/{MARKET_TYPE}/monthly/aggTrades/{SYMBOL}/{zip_filename}"
            output_parquet_path = PQT_FOLDER / f"{file_name}.parquet"

            month_pbar.set_postfix_str(f"Fetching {zip_filename}")

            response = requests.get(url, stream=True)

            if response.status_code == 404:
                tqdm.write(
                    f"⚠️  File not found on Binance Vision (404): {zip_filename}"
                )
                continue
            elif response.status_code != 200:
                tqdm.write(
                    f"❌ Failed to download {zip_filename} (Status: {response.status_code})"
                )
                continue

            total_size = int(response.headers.get("content-length", 0))
            temp_zip_file = tmp_path / zip_filename

            # Download progress bar for the individual file stream
            with open(temp_zip_file, "wb") as f, tqdm(
                desc=f"Downloading {zip_filename}",
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

            # Extract CSV from Zip
            with zipfile.ZipFile(temp_zip_file, "r") as z:
                csv_members = [
                    name for name in z.namelist() if name.endswith(".csv")
                ]
                if not csv_members:
                    tqdm.write(f"⚠️  No CSV found in {zip_filename}")
                    continue

                extracted_csv_path = Path(z.extract(csv_members[0], tmp_path))

            month_pbar.set_postfix_str(f"Converting to Parquet...")

            # Stream extracted CSV into Parquet with DuckDB
            csv_str = extracted_csv_path.as_posix()
            pqt_str = output_parquet_path.as_posix()

            query = f"""
                COPY (SELECT * FROM read_csv_auto('{csv_str}'))
                TO '{pqt_str}'
                (FORMAT 'parquet', COMPRESSION 'zstd');
            """
            duckdb.sql(query)

            # Clean up temp files
            temp_zip_file.unlink(missing_ok=True)
            extracted_csv_path.unlink(missing_ok=True)

            tqdm.write(f"✅ Converted and saved: {output_parquet_path.name}")

    total_time = time.time() - total_start_time
    print(
        f"\nFinished! Total execution time: {total_time:.2f} seconds across {len(months)} month(s)."
    )


if __name__ == "__main__":
    download_and_convert()