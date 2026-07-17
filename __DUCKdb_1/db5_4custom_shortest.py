import pandas as pd
import duckdb
from pathlib import Path

# file source/path
pqt_file_path = Path(__file__).resolve().parent.parent/'__DUCKdb_1' / \
    '_inputs'/'pqt_folder'/'SOLUSDT-aggTrades-2026-07-08.parquet'

# duckdb connection
conn = duckdb.connect(database=":memory:")

# the sql query

qry = f"""--sql
SELECT
    time_bucket(INTERVAL '5 Minutes', epoch_ms(CAST(transact_time AS BIGINT))) AS transact_time,
    arg_min(price, transact_time) AS tde1_price,
    arg_max(price, transact_time) AS last_price,
    sum(CASE WHEN is_buyer_maker = FALSE THEN (price * quantity) ELSE 0.0 END) AS buyVol_usdt,
    sum(CASE WHEN is_buyer_maker = TRUE  THEN (price * quantity) ELSE 0.0 END) AS sellVol_usdt
FROM read_parquet('{pqt_file_path}')
GROUP BY 1
ORDER BY 1 ASC;
"""

df = conn.execute(qry).df()
print(df.head())
