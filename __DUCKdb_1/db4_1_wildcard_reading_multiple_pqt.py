import pandas as pd
import duckdb
from pathlib import Path

# READING MULTIPLE PARQUET FILES

# file path
pqt_file = Path(__file__).resolve().parent.parent / \
    '__DUCKdb_1'/'_inputs'/'pqt_folder'
# wildcard path

# wildcard_path = pqt_file.glob('*.parquet')
# notic how we leave out glob in this scenario
wildcard_path = pqt_file/'*.parquet'

# make it string
wildcard_pth = wildcard_path.as_posix()

# connection to duckdb
conn = duckdb.connect()

# QUERY ALL FILES ONCE AND LOAD THEM INTO DATAFRAME

# OPTION A)-----------------
# df = conn.sql(f"select * from read_parquet('{wildcard_pth}')").df()

# OPTION B) ------------------------------
# ------------- if you need it in order of the files' filenames ----------
# query = f"""
#     SELECT * EXCLUDE (filename)
#     FROM read_parquet('{wildcard_pth}', filename=True)
#     ORDER BY filename ASC, transact_time ASC

# """
# df = conn.sql(query).df()
# EXCLUDE (filename) : Removes the filename column that would have printed with the dataframe

# OPTION C ----------------------------------------
# Find and sort the file paths chronologically in Python
# sorted() ensures '2026-07-01' comes before '2026-07-02', etc.

sorted_files = sorted([f.as_posix() for f in pqt_file.glob('*.parquet')])

df = conn.sql(f"""--sql  
              select * from read_parquet({sorted_files}) """).df()


# -----------------------------------------------------------

# verify the size of the loaded dataset
print(f"loaded {len(df)} rows \n{df.shape[1]} columns : from multiple files")

print(df.tail())


# ----------- VERSION 1  -------------------------------------


# OBSERVE THE SYNTAX -- FOR each option
