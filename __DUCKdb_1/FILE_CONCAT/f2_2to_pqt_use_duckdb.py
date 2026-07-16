import pandas as pd
import duckdb
from pathlib import Path


# -------  CONVERTING CSV TO PARQUET ------------ using DUCKDB
# location of the csv file
folder = Path(__file__).resolve().parent.parent/'_inputs'
btc_file_csv = folder/'BTCUSDT-aggTrades-2026-02.csv'

# parquet return folder
# parquet_file = folder/'sol_pqt_3.parquet'

# --------------------------------------------------------------------------------
# ensure the folder exists before writing or to create it if it doesn't exist
folder.mkdir(parents=True, exist_ok=True)
# -------------------------------------------------------------------------------

test_folder =Path(__file__).resolve().parent.parent/'_inputs'/'crypto_trades_pqt'
test_folder.mkdir(parents=True, exist_ok=True)
parquet_file = test_folder/'BTCUSDT-aggTrades-2026-02.parquet'


def convert_csv_to_parquet(csv_path : Path, parquet_path:Path):
    query = f"""COPY(select * from read_csv_auto('{csv_path}'))
        to '{parquet_path}'
        (format 'parquet', compression 'zstd'); """
    
    # duckdb.execute(query=query)
    duckdb.sql(query=query)

    print('conversion complete')


if __name__ == "__main__":
    convert_csv_to_parquet(btc_file_csv, parquet_file)

# RETURNING THE SIZE OF THE FILES ------------------------------------------------
    if parquet_file.exists():

        size_m = btc_file_csv.stat().st_size / (1024 * 1024)
        print(f"original csv : {btc_file_csv.name} ({size_m:.2f} MB)")

        size_mb = parquet_file.stat().st_size / (1024 * 1024)
        print(f"Success! Created: {parquet_file.name} ({size_mb:.2f} MB)")
