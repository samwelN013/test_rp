import duckdb
import zipfile
import tempfile
from pathlib import Path
import time

# 1. Where are the files?
folder = Path(__file__).resolve().parent.parent / '_inputs' / 'crypto_trades'
pqt_folder = Path(__file__).resolve().parent.parent / '_inputs' / 'pqt_folder'

pqt_folder.mkdir(parents=True, exist_ok=True)

# 2. Get sorted list of ZIP files
sorted_zip_files_source = sorted(folder.glob("*.zip"))

start_time = time.time()

# Create a temporary directory to unpack files into during conversion
with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)

    for zip_file in sorted_zip_files_source:
        # Determine output filename
        stem_name = zip_file.name[:-4] if zip_file.name.endswith('.zip') else zip_file.stem
        if stem_name.endswith('.csv'):
            stem_name = stem_name[:-4]
            
        parquet_path = pqt_folder / f"{stem_name}.parquet"

        # Open the zip file and extract the CSV file inside
        with zipfile.ZipFile(zip_file, 'r') as z:
            csv_members = [f for f in z.namelist() if f.endswith('.csv')]
            if not csv_members:
                print(f"Skipping {zip_file.name}: No CSV inside.")
                continue
            
            # Extract CSV to temporary folder
            extracted_csv_path = Path(z.extract(csv_members[0], tmp_path))

        # Pass extracted CSV path to DuckDB
        csv_str = extracted_csv_path.as_posix()
        pqt_str = parquet_path.as_posix()

        query = f"""
            COPY (SELECT * FROM read_csv_auto('{csv_str}'))
            TO '{pqt_str}'
            (FORMAT 'parquet', COMPRESSION 'zstd');
        """
        duckdb.sql(query)

        # Clean up temporary file to conserve disk space
        extracted_csv_path.unlink(missing_ok=True)

        print(f"Converted: {zip_file.name} -> {parquet_path.name}")

time_taken = time.time() - start_time
print(f"Time taken: {time_taken:.2f} seconds")