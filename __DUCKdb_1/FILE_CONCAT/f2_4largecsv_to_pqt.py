import duckdb
from pathlib import Path

# ------- CONFIGURING PATHS ------------
folder = Path(__file__).resolve().parent.parent / '_inputs' / 'crypto_trades'
btc_file_csv = folder / 'BTCUSDT-aggTrades-2026-02.csv'

test_folder = Path(__file__).resolve().parent.parent / '_inputs' / 'crypto_test_f'
test_folder.mkdir(parents=True, exist_ok=True)
parquet_file = test_folder / 'btc_feb_2026.parquet'

def convert_csv_to_parquet_turbo(csv_path: Path, parquet_path: Path):
    # Convert paths to posix format for SQL safety
    csv_str = csv_path.as_posix()
    parquet_str = parquet_path.as_posix()
    
    # Establish local connection
    conn = duckdb.connect()
    
    # --- PERFORMANCE TWEAKS ---
    # 1. Disable insertion order tracking to allow massive multi-core write parallelism
    conn.execute("SET preserve_insertion_order = false;")
    
    # 2. Use all available CPU cores (optional, DuckDB defaults to total cores, but good to force)
    conn.execute("SET threads = 8;")  # Adjust to your PC's CPU core count
    
    # 3. Explicitly define schema (bypasses CSV auto-detect scanner overhead)
    # Example Binancy aggTrades schema: agg_trade_id, price, qty, first_trade_id, last_trade_id, timestamp, is_buyer_maker
    # schema_types = {
    #     'aggregate_trade_id': 'BIGINT',
    #     'price': 'DOUBLE',
    #     'quantity': 'DOUBLE',
    #     'first_trade_id': 'BIGINT',
    #     'last_trade_id': 'BIGINT',
    #     'timestamp': 'TIMESTAMP_MS',  # Crypto timestamps are usually in ms
    #     'is_buyer_maker': 'BOOLEAN',
    #     'is_best_match': 'BOOLEAN'
    # }
    
    # Constructing query with explicit schema mapping
    query = f"""
        COPY (
            SELECT * FROM read_csv_auto(
                '{csv_str}'
            )
        )
        TO '{parquet_str}'
        (FORMAT 'parquet', COMPRESSION 'zstd');
    """
    
    print(f"⚡ Turbo-converting {csv_path.name} to {parquet_path.name}...")
    conn.execute(query)
    print('✅ Conversion complete!')

if __name__ == "__main__":
    if btc_file_csv.exists():
        convert_csv_to_parquet_turbo(btc_file_csv, parquet_file)
        
        # Verify sizes
        csv_sz = btc_file_csv.stat().st_size / (1024 * 1024)
        pqt_sz = parquet_file.stat().st_size / (1024 * 1024)
        print(f"Original CSV : {btc_file_csv.name} ({csv_sz:.2f} MB)")
        print(f"Parquet File : {parquet_file.name} ({pqt_sz:.2f} MB)")

        
# --------------  CAN EVEN STICK TO THE FISRT METHOD --------------------------------