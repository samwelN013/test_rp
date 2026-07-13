import duckdb
import pandas as pd
from pathlib import Path
# pip install polars
import polars

# FILE PATH
cwd = Path(__file__).resolve()
csvfile = cwd.parent/'_inputs'/'postcsv.csv'
#database path
data_base = cwd.parent/'_inputs'/'db_learn1.db'
# connection
conn = duckdb.connect()  # the temporary connection

# conn= duckdb.connect('db_learn1.db') # persistent connection
conn= duckdb.connect(data_base) # persistent connection
#
# --import data, --create table -- selected and print-- using 'execute()'

# A) ---absolute file path ===========================================

conn.execute("create table if not exists aggts as select * from 'postcsv.csv' ")
conn.execute("create table if not exists samlearn1 (id int primary key, name varchar(255), age int)")

tables = duckdb.sql('show tables', connection= conn)
des=duckdb.sql('describe samlearn1', connection=conn)
# print(tables)

# conn.execute("insert into samlearn1 values (1,'kenney', 23),(2,'samwel', 24), (3, 'nyanj', 25)")
# conn.execute("drop table samlearn1")

# me = conn.execute("select * from samlearn1").df()
# print(me)

# B) ---relative file path ===========================================
conn.execute(f"create table if not exists csvtest1 as select * from read_csv('{csvfile}') ")
table2 =conn.execute("select * from csvtest1  ").df()
print(table2)