import pandas as pd
import duckdb
from pathlib import Path

# reading multiple files version 2
# file path
pqt_folder = Path(__file__).resolve().parent.parent / \
    '__DUCKdb_1'/'_inputs'/'pqt_folder'
# parquet file list
pqt_list = [file.as_posix() for file in pqt_folder.glob('*.parquet')]

# connection
conn = duckdb.connect()

# Duckdb natively understands python lists of paths
df = conn.sql(f"select * from read_parquet({pqt_list})").df()

# print(df.tail())

# --------------- RETURNS NUMBER OF FILES YOU'RE WORKING WITH ---------
print(f"Dealing with: {len(pqt_list)} files --and --\n{len(df)} rows")

# -------------- VERSION 2 --------------------------------

#                   END
