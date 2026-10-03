import duckdb
import zipfile
import pandas as pd
from pathlib import Path
import time

folder = Path(__file__).resolve().parent.parent / '_inputs' / 'crypto_trades'
pqt_folder = Path(__file__).resolve().parent.parent / '_inputs' / 'pqt_folder'
pqt_folder.mkdir(parents=True, exist_ok=True)

sorted_zip_files_source = sorted(folder.glob("*.zip"))

start_time = time.time()

for zip_file in sorted_zip_files_source:
    stem_name = zip_file.name[:-4] if zip_file.name.endswith('.zip') else zip_file.stem
    if stem_name.endswith('.csv'):
        stem_name = stem_name[:-4]
        
    parquet_path = pqt_folder / f"{stem_name}.parquet"

    with zipfile.ZipFile(zip_file, 'r') as z:
        csv_members = [f for f in z.namelist() if f.endswith('.csv')]
        if not csv_members:
            continue
            
        with z.open(csv_members[0]) as csv_file:
            # Read CSV stream into Pandas
            df = pd.read_csv(csv_file)
            
            # Write Pandas DataFrame to Parquet using DuckDB
            pqt_str = parquet_path.as_posix()
            query = f"""
                COPY df TO '{pqt_str}' (FORMAT 'parquet', COMPRESSION 'zstd');
            """
            duckdb.sql(query)

    print(f"Converted: {zip_file.name} -> {parquet_path.name}")

time_taken = time.time() - start_time
print(f"Time taken: {time_taken:.2f} seconds")