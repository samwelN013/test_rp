import duckdb
import pandas as pd
from pathlib import Path
# pip install polars
import polars

# FILE PATH
cwd = Path(__file__).resolve()
csvfile = cwd.parent/'_inputs'/'postcsv.csv'
# database path
data_base = cwd.parent/'_inputs'/'duck_databases'/'db_learn1.db'
# connection
conn = duckdb.connect(data_base)  # persistent connection
#
# --import data, --create table -- selected and print-- using 'duckdb.sql()''

# A) ---absolute file path ===========================================

# duckdb.sql("create table if not exists aggts_duck as select * from 'postcsv.csv' ") # if it's temporary; always add , connection = conn (if you want your data to remain in a database) ie

duckdb.sql(
    "create table if not exists aggts_duck as select * from 'postcsv.csv' ", connection=conn)

duckdb.sql("create table if not exists samlearn1_duck (id int primary key, name varchar(255), age int)", connection=conn)

# ---------------------------------------------------------

tables = duckdb.sql('show tables', connection=conn)
# des=duckdb.sql('describe samlearn1', connection=conn)
# print(tables)

# duckdb.sql("insert into samlearn1_duck values (1,'kenney', 23),(2,'samwel', 24), (3, 'nyanj', 25)", connection= conn)
# duckdb.sql("drop table samlearn1")

# you don't need the function .df(), now that u ar using duckdb.sql
me = duckdb.sql("select * from samlearn1_duck ", connection= conn)
# print(me)

# B) ---relative file path ===========================================

# b) option 1 : of passing the file path --------------------------------------
duckdb.sql(f"create table if not exists csvtest1_duck as select * from read_csv('{csvfile}') ")

# b) option 2 : of passing the python variable assigned to the file path ie -----
mkt_data = duckdb.read_csv(csvfile)

duckdb.sql(f"create table if not exists csvtest1_dk2 as select * from mkt_data ")

table2 =duckdb.sql("select * from csvtest1_dk2 limit 7 ")

print(table2)
