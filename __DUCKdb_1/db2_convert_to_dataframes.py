import duckdb
import pandas as pd
from pathlib import Path
# pip install polars
# import polars

# FILE PATH
cwd = Path(__file__).resolve()
csvfile = cwd.parent/'_inputs'/'postcsv.csv'

# ---- CONNECTION TO DUCKDB --------------------------------------------------------
conn = duckdb.connect()  # in memory mode - discard when we exit the python file

mkt_data = duckdb.read_csv(csvfile)

# ----------------------------------------------------------------------------
# CONVERT THE DUCKDB DATA FILE TO PANDAS df : use the data.df() function ================
df = mkt_data.df()

# print(df.head())

# CONVERTING TO A POLARS data.pl() function ===============================
p_df = mkt_data.pl()
# print(p_df) # This is the polars dataframe returned

# CONVERTING TO ARRROWS : data.arrow() ====================
d_arrow = mkt_data.arrow()
# print(d_arrow)

# CONVERT DATA TO NUMPY ARRAY  : data.fetchnumpy() ==================
d_nmp =mkt_data.fetchnumpy() 
# print(d_nmp)

# CONVERT TO PYTHON OBJECTS : data.fetchall()
# --- and each object in the dataframe is a TUPLE

p_objt= mkt_data.fetchone() # to return a single object out of the entire object; a single tuple
p_objt = mkt_data.fetchall() # returns all the tuples
# print(p_objt)
