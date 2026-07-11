import pandas as pd
import numpy as np
from pathlib import Path
import duckdb
import glob
import time
import polars

# FILE PATH
# cwd = Path.cwd()
cwd = Path(__file__).resolve()
csvfile = cwd.parent.parent/'_1inputs'/'postcsv.csv'

my_1st_db = cwd.parent.parent/'_5outputs'/'my_1st.db'
# -------------------------------------------
# CREATE DUCKDB CONNECTION

conn = duckdb.connect()
# connect() - creates a new memory database by default ; then data will be lost when you exit the python process

# ----------------------------------------
# TO pass the data on disc, you need to pass the name of the database, then data will remain saved when you exit the file
# conn = duckdb.connect("my_1st.db")
# conn = duckdb.connect(my_1st_db)

# print(my_1st_db)
# ----------------------------------------
# if you want no inserts or updata; read_only = True
# conn = duckdb.connect("my_1st.db", read_only=True)
