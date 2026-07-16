import duckdb
from pathlib import Path
import time

# ----- CONFIGURING PATHS -----
folder = Path(__file__).resolve().parent.parent / '_inputs' / 'crypto_trades'
pqt_folder = Path(__file__).resolve().parent.parent / '_inputs' / 'pqt_folder'

# Ensure the output directory exists
pqt_folder.mkdir(parents=True, exist_ok=True)

# Gather and sort all CSV files
sorted_csv_files_source = sorted(folder.glob("*.csv"))


def batch_convert_csv_to_parquet(csv_list: list[Path], output_dir: Path):
    """
    Loops through a list of CSV files and uses DuckDB to convert
    each one into a highly compressed Parquet file inside output_dir.
    """
    if not csv_list:
        print("⚠️ No CSV files found to convert.")
        return

    # Start a single DuckDB connection to reuse across all files
    conn = duckdb.connect()
    
    # --- PERFORMANCE OPTIMIZATION ---
    # Disable strict order tracking to allow massive multi-threaded parallel writes
    conn.execute("SET preserve_insertion_order = false;")
    
    print(f"🚀 Found {len(csv_list)} files to convert. Starting batch processing...\n")
    start_time = time.time()

    for idx, csv_path in enumerate(csv_list, start=1):
        # 1. Create the destination path (keep name, swap extension to .parquet)
        parquet_path = output_dir / csv_path.with_suffix('.parquet').name
        
        # 2. Format paths safely for SQL (avoids Windows backslash escape issues)
        csv_str = csv_path.as_posix()
        pqt_str = parquet_path.as_posix()
        
        # 3. Construct and run the query
        query = f"""
            COPY (SELECT * FROM read_csv_auto('{csv_str}'))
            TO '{pqt_str}'
            (FORMAT 'parquet', COMPRESSION 'zstd');
        """
        
        file_start = time.time()
        print(f"[{idx}/{len(csv_list)}] Converting: {csv_path.name}...")
        
        try:
            conn.execute(query)
            
            # 4. Calculate file size and speed stats
            file_elapsed = time.time() - file_start
            csv_size_mb = csv_path.stat().st_size / (1024 * 1024)
            pqt_size_mb = parquet_path.stat().st_size / (1024 * 1024)
            reduction = ((csv_size_mb - pqt_size_mb) / csv_size_mb) * 100
            
            print(f"   ↳ Done in {file_elapsed:.2f}s | {csv_size_mb:.1f}MB -> {pqt_size_mb:.1f}MB (-{reduction:.1f}%)")
            
        except Exception as e:
            print(f"   ❌ Failed to convert {csv_path.name}. Error: {e}")

    total_elapsed = time.time() - start_time
    print(f"\n🎉 All conversions complete! Total time: {total_elapsed:.2f} seconds.")


if __name__ == "__main__":
    batch_convert_csv_to_parquet(sorted_csv_files_source, pqt_folder)