
with rawdata as (
    select
        epoch_ms(cast(transact_time as bigint)) as ts,
        price,
        quantity,
        (price * quantity ) quote_qty_usdt,
        is_buyer_maker
    from read_parquet("C:\Users\user\Desktop\test_repo\__DUCKdb_1\_inputs\pqt_folder\SOLUSDT-aggTrades-2026-07-08.parquet")
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
group by 1
order by transact_time asc;
