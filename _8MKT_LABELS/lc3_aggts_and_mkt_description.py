import time
from datetime import datetime
from binance.client import Client
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
print('hello money')

# FILE PATH and SQL QUERY


# file path
folder = Path(__file__).resolve().parent / '_inputs'/'sol_monthly_aggts_2026'
# access the files
sorted_pqt_files = sorted(folder.glob('*.parquet'))
# file list
pqt_file = [pqt.as_posix() for pqt in sorted_pqt_files]



# LOAD  aggregated DATA TO dataframe with  DUCKDB

conn = duckdb.connect(database=":memory:")

qry = f"""--sql
SELECT
    time_bucket(INTERVAL '5 Minutes', epoch_ms(CAST(transact_time AS BIGINT))) AS transact_time,
    arg_min(price, transact_time) AS tde1_price,
    arg_max(price, transact_time) AS last_price,
    sum(CASE WHEN is_buyer_maker = FALSE THEN (price * quantity) ELSE 0.0 END) AS buyVol_usdt,
    sum(CASE WHEN is_buyer_maker = TRUE  THEN (price * quantity) ELSE 0.0 END) AS sellVol_usdt
FROM read_parquet({pqt_file})
GROUP BY 1
ORDER BY 1 ASC;
"""

bdf = conn.execute(qry).df()
conn.close()

print(bdf.tail())


