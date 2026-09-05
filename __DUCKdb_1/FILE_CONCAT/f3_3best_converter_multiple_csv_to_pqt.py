import duckdb
from pathlib import Path
import time

# 1. Where are the files?
folder = Path(__file__).resolve().parent.parent / '_inputs' / 'crypto_trades'
pqt_folder = Path(__file__).resolve().parent.parent / '_inputs' / 'pqt_folder'

# Make sure the output folder exists
pqt_folder.mkdir(parents=True, exist_ok=True)

# 2. Get our list of sorted CSV files
sorted_csv_files_source = sorted(folder.glob("*.csv"))

start_time = time.time()
# 3. Loop through each CSV file one by one and convert it
for csv in sorted_csv_files_source:
    
    # Create the new parquet filename (swaps .csv for .parquet)
    new_filename = csv.with_suffix('.parquet').name
    parquet_path = pqt_folder / new_filename
    
    # Convert paths to safe strings for SQL (replaces "\" with "/")
    csv_str = csv.as_posix()
    pqt_str = parquet_path.as_posix()
    
    # Run the DuckDB command directly
    query = f"""
        COPY (SELECT * FROM read_csv_auto('{csv_str}'))
        TO '{pqt_str}'
        (FORMAT 'parquet', COMPRESSION 'zstd');
    """
    duckdb.sql(query)
    
    print(f"Converted: {csv.name} -> {new_filename}")

time_taken = (time.time()) - start_time
print(f"Time taken: {time_taken:.2f} seconds")
