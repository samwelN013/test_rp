import duckdb
import pandas as pd
from pathlib import Path
# pip install polars
import polars

# FILE PATH
cwd = Path(__file__).resolve()
csvfile = cwd.parent/'_inputs'/'postcsv.csv'

# ---- CONNECTION TO DUCKDB --------------------------------------------------------
conn = duckdb.connect()  # in memory mode - discard when we exit the python file
conn.execute('select 42').fetchone()
# print(num)


# ----- IMPORTING CSV DATA ---------- -----------------------------------------------
# mtd 1  : of file located in the parent folder
data1 = duckdb.sql("select  * from 'postcsv.csv' ")
# print(data1)

# mtd 2 : of the read_csv function , that reads even relative file paths
_csv = duckdb.read_csv(csvfile)
# print(_csv)

# ---MTD 3: uses the select functions with the relative file path
# mtd 3_a)
data2 = duckdb.sql("select * from 'postcsv.csv' ")
# print(data2)

# mtd 3_b)
data3 = duckdb.sql("select * from _csv ")
# print(data3)

# --------------------------------------------------------------------------------
#   modifications on reading CSV reading

mktdata = duckdb.read_csv(csvfile, header=False, skiprows=1)
# print(mktdata)
data4 = duckdb.sql("select * from mktdata")
# print(data)

# -------------------------------------------------------------------------------
# returning the type of the database
my_type = type(data3)
print(my_type)  # returns  <class '_duckdb.DuckDBPyRelation'>

# ----------------------------------------------------------------------------
# CONVERT THE DUCKDB DATA FILE TO PANDAS df : use the data.df() function
df = data3.df()
# print(df.head())

# ------------- ---------

# MOVE THE NEXT py file 't2'.
