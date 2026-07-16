import pandas as pd
import duckdb
from pathlib import Path


# -------  CONVERTING CSV TO PARQUET ------------ using PANDAS
# location of the csv file
folder = Path(__file__).resolve().parent.parent/'_inputs'/'crypto_trades'
btc_file_csv = folder/'SOLUSDT-aggTrades-2026-07-07.csv'

# parquet return folder
parquet_file = folder/'sol_pqt_1.parquet'

# ensure the folder exists before writing
folder.mkdir(parents=True, exist_ok=True)


def convert_csv_to_parquet(csv_path: Path, parquet_path: Path):
    # read csv into dataframe
    df = pd.read_csv(csv_path)

    # save parquet using the fast parquet or pyarrow engine (zstd compression best)
    df.to_parquet(parquet_path, engine='pyarrow', compression='zstd')
    print('conversion complete')


if __name__ == "__main__":
    convert_csv_to_parquet(btc_file_csv, parquet_file)

# RETURNING THE SIZE OF THE FILES
    if parquet_file.exists():

        size_m = btc_file_csv.stat().st_size / (1024 * 1024)
        print(f"original csv : {btc_file_csv.name} ({size_m:.2f} MB)")

        size_mb = parquet_file.stat().st_size / (1024 * 1024)
        print(f"Success! Created: {parquet_file.name} ({size_mb:.2f} MB)")
