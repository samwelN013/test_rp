import pandas as pd
import duckdb
from pathlib import Path

# -------  CONVERTING CSV TO PARQUET ------------
# location of the csv file
folder = Path(__file__).resolve().parent.parent/'_inputs'/'crypto_trades'
btc_file_csv = folder/'SOLUSDT-aggTrades-2026-07-07.csv'

#convert to parquet and save it there
parquet_file = folder/'SOLUSDT1.parquet'

conn = duckdb.connect()

conn.execute(""" copy (
             select * from read_csv_auto(?) )
             to ?
             (format parquet, compression zstd) """, [str(btc_file_csv), str(parquet_file)])
