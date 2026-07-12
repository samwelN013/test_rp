import duckdb
import pandas as pd
from pathlib import Path
#  --------- IN ANALYTICS, DUCKDB SHINES SINCE IT HAS A COLUMNAR processing engine using SQL
# FILE PATH
cwd = Path(__file__).resolve()
csvfile = cwd.parent/'_inputs'/'postcsv.csv'
# --------------- creates the connection automatically if not manually done
mkt_data = duckdb.read_csv(csvfile)
# ---- u can make a connection to duckdb database -------------- ie
conn = duckdb.connect()

# ===== TABLE CREATTION
# A). with : duckdb.sql() function -------------------
duckdb.sql(
    f"create table if not exists aggtrades1 as select * from read_csv('{csvfile}') ", connection=conn) 
# aggtrades = duckdb.sql("select price from aggtrades1 limit 7")
# print(aggtrades)
# ----- converted to pandas dataframe .df()
duckdb.sql("select price from aggtrades1 limit 7", connection=conn).df()
# print(aggtrades.head())

# B).  with conn.execute() function ----------------------------

# WORKED well ; you must include a df() function at the end, or pl- for polar, or fetchone/all()- for py, or numpy function.

# trades = conn.execute(" select * from 'postcsv.csv' ").df() # this works
# trades = conn.execute("select * from mkt_data ").df()  # failed
# trades = conn.execute("select * from aggtrades1 ")  # failed

# trades = conn.execute(f"select * from read_csv('{csvfile}')").df()
trades = conn.execute("select * from aggtrades1 ").df()

# print(trades.head())

# # to return info about my schema or database, ie the list of tables i have created : ALMOST DONE
# # infor about a specific table : DONE
# global parqueting/ csv_ing  
# Easily converting files from csv to parquet.


