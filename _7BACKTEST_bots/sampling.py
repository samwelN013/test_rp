import pandas as pd
import numpy as np
import json
import csv
import duckdb
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime

# ==============================================================================
# 1. CONFIGURATION & FILE PATHS
# ==============================================================================
stt = datetime.now() # start time

# Setup paths based on the current file's location
cwd = Path(__file__).resolve()
this_folder = cwd.parent.parent

# Input Data
# DATA_FILE = data_folder / 'SOLUSDT-1m-2026-06-02.csv'
DATA_FILE = this_folder / '_1inputs' / 'WLDUSDT-1m-2024-12.csv'

# Output Files
#---------------ensure out put folder exists
out_folder = this_folder/'_5outputs'
out_folder.mkdir(parents=True, exist_ok=True)

# symbol name
SYMBOL = DATA_FILE.name.split("-")[0] # ie WLDUSDT
timenow= datetime.now().strftime("%d_%H%M%S")

JOURNAL_FILE = out_folder/ f"{SYMBOL}_journal-{timenow}.csv"
STATS_FILE = out_folder/f"{SYMBOL}_stats-{timenow}.json" 
EQUITY_CHART = out_folder/f"{SYMBOL}_equitycurve-{timenow}.png"

conn = duckdb.connect(":memory:")
qry = f"""--sql
    select 
    open_time,
    open,
    high,
    low,
    close,
    volume,
    close_time,
    quote_volume
    from read_csv('{DATA_FILE}')
    """

df= conn.sql(qry).df()
conn.close()

print(df.head())