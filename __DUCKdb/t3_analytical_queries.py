import duckdb
import pandas as pd
from pathlib import Path
#  --------- IN ANALYTICS, DUCKDB SHINES SINCE IT HAS A COLUMNAR processing engine using SQL
# FILE PATH
cwd = Path(__file__).resolve()
csvfile = cwd.parent/'_inputs'/'postcsv.csv'
# --------------- creates the connection automatically if not manually done
mkt_data = duckdb.read_csv(csvfile)
#---- u can make a connection to duckdb database -------------- ie
conn= duckdb.connect()

# ===== TABLE CREATTION
aggts1 = duckdb.sql(
    "create table if not exists aggtrades1 as select * from mkt_data ")

aggtrades = duckdb.sql("select * from aggtrades1")
# aggtrades = conn.execute(" select * from mkt_data") # FAILD

# to return info about my schema or database, ie the list of tables i have created
# infor about a specific table
print(aggtrades)

#  =========== TABLE INFO QUERY ===============
info = duckdb.sql(
    "SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'aggtrades1' ")
# print(info)
# ------------------------------------------------------
