from pathlib import Path
import duckdb
import pandas as pd

# Define your file path using pathlib
parquet_file_path = Path(__file__).resolve().parent.parent /'__DUCKdb_1'/'_inputs'/'pqt_folder'/'SOLUSDT-aggTrades-2026-07-08.parquet'

# 1. Establish an in-memory DuckDB connection
conn = duckdb.connect(database=":memory:")

# 2. Write the SQL query to do the heavy lifting
# We use time_bucket for fast grouping, and arg_min/arg_max to get open (first) and close (last) prices.
query = f"""--sql
WITH raw_data AS (
    SELECT 
        -- Convert millisecond epoch to timestamp
        epoch_ms(CAST(transact_time AS BIGINT)) AS ts,
        price,
        quantity,
        -- Calculate quote quantity (price * quantity/base_qty)
        (price * quantity) AS quote_qty_usdt,
        is_buyer_maker
    FROM read_parquet('{parquet_file_path.as_posix()}')
),
processed_volumes AS (
    SELECT 
        ts,
        price,
        -- If is_buyer_maker is False, it's a taker buy (buyer-initiated)
        CASE WHEN is_buyer_maker = FALSE THEN quote_qty_usdt ELSE 0.0 END AS buy_vol_usdt,
        -- If is_buyer_maker is True, it's a taker sell (seller-initiated)
        CASE WHEN is_buyer_maker = TRUE THEN quote_qty_usdt ELSE 0.0 END AS sell_vol_usdt
    FROM raw_data
)
SELECT 
    time_bucket(INTERVAL '5 Minutes', ts) AS transact_time,
    -- Get the first and last price in the 5-minute bucket based on the timestamp
    arg_min(price, ts) AS tde1_price,
    arg_max(price, ts) AS last_price,
    sum(buy_vol_usdt) AS buyVol_usdt,
    sum(sell_vol_usdt) AS sellVol_usdt
FROM processed_volumes
GROUP BY 1
ORDER BY transact_time ASC;
"""

# 3. Execute the query and instantly export the result to a Pandas DataFrame
bdf = conn.execute(query).df()

# Close the connection
conn.close()

# --- Back in Pandas Land ---
# bdf is now a highly compressed 5-minute aggregated DataFrame.
# You can easily add your custom derived columns here!
# For example:
bdf['total_vol_usdt'] = bdf['buyVol_usdt'] + bdf['sellVol_usdt']
bdf['vol_imbalance'] = bdf['buyVol_usdt'] - bdf['sellVol_usdt']

print(bdf.tail())