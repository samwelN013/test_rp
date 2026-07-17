-- 1. Create a CTE to parse raw millisecond timestamps and calculate base quantities
WITH base_data AS (
    SELECT 
        epoch_ms(CAST(transact_time AS BIGINT)) AS ts,
        price,
        quantity,
        (price * quantity) AS quote_qty_usdt,
        is_buyer_maker
    FROM read_parquet("C:\Users\user\Desktop\test_repo\__DUCKdb_1\_inputs\pqt_folder\SOLUSDT-aggTrades-2026-07-08.parquet") 
    -- Tip: Use forward slashes (/) even on Windows for paths inside DuckDB
),

-- 2. Separate into distinct Buy vs Sell volume rows based on the buyer_maker flag
volume_split AS (
    SELECT 
        ts,
        price,
        CASE WHEN is_buyer_maker = FALSE THEN quote_qty_usdt ELSE 0.0 END AS buy_vol,
        CASE WHEN is_buyer_maker = TRUE  THEN quote_qty_usdt ELSE 0.0 END AS sell_vol
    FROM base_data
)

-- 3. Execute 5-minute bucketing, OHLC-style price tracking, and aggregate volumes
SELECT 
    time_bucket(INTERVAL '5 Minutes', ts) AS transact_time,
    arg_min(price, ts) AS open_price,       -- First price in the 5m window
    max(price)         AS high_price,       -- Highest price in the 5m window
    min(price)         AS low_price,        -- Lowest price in the 5m window
    arg_max(price, ts) AS close_price,      -- Last price in the 5m window
    sum(buy_vol)       AS buyVol_usdt,
    sum(sell_vol)      AS sellVol_usdt
FROM volume_split
GROUP BY 1
ORDER BY transact_time ASC
LIMIT 100; -- Limit preview rows while testing to keep rendering instant