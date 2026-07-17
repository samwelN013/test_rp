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
with rawdata as (
    select
        epoch_ms(cast(transact_time as bigint)) as ts,
        price,
        quantity,
        (price * quantity ) quote_qty_usdt,
        is_buyer_maker
    from read_parquet('{pqt_file_path}')
),
processed_data as(
    select
        ts,
        price,
        case when is_buyer_maker = FALSE THEN quote_qty_usdt else 0.0 end as buy_vol_usdt,
        case when is_buyer_maker = TRUE THEN quote_qty_usdt else 0.0 end as sell_vol_usdt
    from rawdata
)
select
    time_bucket(interval '5 Minutes', ts) as transact_time,
    arg_min(price, ts) as tde1_price,
    arg_max(price, ts) as last_price,
    sum(buy_vol_usdt) as buyVol_usdt,
    sum(sell_vol_usdt) as sellVol_usdt
from processed_data
GROUP BY time_bucket(INTERVAL '5 Minutes', ts)
order by transact_time asc;
"""
df = conn.execute(qry).df()
print(df.head())
