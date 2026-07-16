import pandas as pd
import duckdb
from pathlib import Path

# ------- CONFIGURING PATHS ------------
folder = Path(__file__).resolve().parent.parent / '_inputs' / 'crypto_trades'
btc_file_csv = folder / 'SOLUSDT-aggTrades-2026-07-07.csv'
parquet_file = folder / 'SOLUSDT3.parquet'

# Ensure folder exists
folder.mkdir(parents=True, exist_ok=True)

# 1. Establish the connection
conn = duckdb.connect()

# 2. Safely convert paths to Posix strings (replaces Windows "\" with "/")
csv_str = btc_file_csv.as_posix()
parquet_str = parquet_file.as_posix()

# 3. Construct the query using clean string formatting
query = f"""
    COPY (SELECT * FROM read_csv_auto('{csv_str}'))
    TO '{parquet_str}'
    (FORMAT 'parquet', COMPRESSION 'zstd');
"""

# 4. Execute the query directly
conn.execute(query)

print("Conversion complete!")

# --- VERIFY SIZES ---
if parquet_file.exists():
    size_m = btc_file_csv.stat().st_size / (1024 * 1024)
    print(f"Original CSV : {btc_file_csv.name} ({size_m:.2f} MB)")

    size_mb = parquet_file.stat().st_size / (1024 * 1024)
    print(f"Success! Created: {parquet_file.name} ({size_mb:.2f} MB)")