import duckdb
import pandas as pd
from pathlib import Path
# pip install polars
import polars

# FILE PATH
cwd = Path(__file__).resolve()
csvfile = cwd.parent/'_inputs'/'postcsv.csv'
# connection
conn = duckdb.connect()  # the temporary connection
#
# --import data, --create table -- selected and print-- using 'execute()'
# A) ---absolute file path

conn.execute("create table if not exists aggts as select * from 'postcsv.csv' ")

