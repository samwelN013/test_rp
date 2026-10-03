import time
from datetime import datetime
from binance.client import Client
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

# FILE PATH and SQL QUERY


# file path
folder = Path(__file__).resolve().parent / '_inputs'/'sol_monthly_aggts_2026'
# access the files
sorted_pqt_files = sorted(folder.glob('*.parquet'))
# file list
pqt_file = [pqt.as_posix() for pqt in sorted_pqt_files]


# LOAD  aggregated DATA TO dataframe with  DUCKDB

conn = duckdb.connect(database=":memory:")

# To bucket into other time buckets; you can simply use minutes, hours, or day; duckdb sql netavely understands them
# ie '5 Minutes', '1 Day', '1 Hour', '4 Hours' etc

# Select your desired timeframe here: '1 Day', '1 Hour', '5 Minutes', '4 Hours', etc.
timeframe = '1 Day'

qry = f"""--sql
SELECT
    time_bucket(INTERVAL '{timeframe}', epoch_ms(CAST(transact_time AS BIGINT))) AS open_time,
    arg_min(price, transact_time) AS open,
    max(price) AS high,
    min(price) AS low,
    arg_max(price, transact_time) AS close,
    time_bucket(INTERVAL '{timeframe}', epoch_ms(CAST(transact_time AS BIGINT))) + INTERVAL '{timeframe}' - INTERVAL '1 millisecond' AS close_time,
    sum(CASE WHEN is_buyer_maker = FALSE THEN (price * quantity) ELSE 0.0 END) AS buyVol_usdt,
    sum(CASE WHEN is_buyer_maker = TRUE  THEN (price * quantity) ELSE 0.0 END) AS sellVol_usdt
FROM read_parquet({pqt_file})
GROUP BY 1
ORDER BY open_time ASC;
"""

df = conn.execute(qry).df()
conn.close()

print(df.tail())
