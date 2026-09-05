from pathlib import Path
import duckdb
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# File path
fld = Path(__file__).resolve().parent.parent / '_8MKT_LABELS' / '_inputs'
# folder = fld / 'dayly_klines'
# folder = fld / 'hourly_klines'
folder = fld / '_5m_klines'

# Access the files
sorted_pqt_files = sorted(folder.glob('*.parquet'))
pqt_file = [pqt.as_posix() for pqt in sorted_pqt_files]

# DuckDB query for the data
conn = duckdb.connect()

query = f"""
        select 
            open_time,
            open,
            high,
            low,
            close,
            close_time
        from read_parquet({pqt_file})    
        order by open_time asc
        """

df = conn.execute(query).df()
conn.close()

# Convert Unix timestamp (ms) to Datetime
df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
df['sma25'] = df['close'].rolling(25).mean()

# ADDING THE PIVOT POINTS TO THE TABLE

left_len = 10
right_len = 10
window_size = left_len + right_len + 1
# Rolling max/min centered on the target candle
rolling_max = df['high'].rolling(window=window_size, center=True).max()
rolling_min = df['low'].rolling(window=window_size, center=True).min()
# Indentify pivot points (hing must equal max of the window and low must equal min of the window )
df['pivot_high'] = df['high'].where(df['high'] == rolling_max, None)
df['pivot_low'] = df['low'].where(df['low'] == rolling_min, None)
# Combined column showing the price level at the swing point, or None otherwise
df['swing_point'] = df['pivot_high'].combine_first(df['pivot_low'])

# Ensure numeric types for Plotly
cols_to_numeric = ['open', 'high', 'low', 'close']
df[cols_to_numeric] = df[cols_to_numeric].apply(pd.to_numeric)

# print(df[0:100].to_string())
# print(df.head())

# DF for PIVOT POINTS ONLY
pv_df = df[df['swing_point'].notna()]

# print(pv_df.to_string())
# print(pv_df.tail())
# print(pv_df)
# print(df.head())

# ===============================================================

# SWING PIVOT POINTS TABLE

# 1. filter out only the candles that formed valid pivots
pivots = df[df['swing_point'].notna()].copy()
# 2. determine pivot type (high or low ) for each pivot point
pivots['type'] = np.where(pivots['pivot_high'].notna(), 'high', 'low')
# 3. Reset index to calculate exact bar index distance between pivots
pivots = pivots.reset_index().rename(columns={'index': 'orig_bar_index'})

# BUILD THE SWING POINTS TABLE (spt)
spt = pd.DataFrame()

# Start & End attributes per move (shift by -1 to pair consecutive pivots)
spt['swing_id'] = range(1, len(pivots))
spt['swing_start_time'] = pivots['open_time'][:-1].values
spt['swing_start_price'] = pivots['swing_point'][:-1].values
spt['swing_end_time'] = pivots['open_time'][1:].values
# spt['swing_end_time'] = pivots['close_time'][1:].values
spt['swing_end_price'] = pivots['swing_point'][1:].values

# bars elapsed between start and end of the swing move
spt['bars'] = (pivots['orig_bar_index'][1:].values -
               pivots['orig_bar_index'][:-1].values)
# percentage price change
spt['price_change_pct'] = (
    (spt['swing_end_price'] - spt['swing_start_price'])/spt['swing_start_price'])*100
# duration of the swing move
spt['duration'] = (spt['swing_end_time'] - spt['swing_start_time'])
# swing direction ; up or down
spt['direction'] = np.where(spt['swing_end_price']
                            > spt['swing_start_price'], 'up', 'down')

# Trend classification (bullish, bearish , ranging)
conditions = [spt['price_change_pct'] > 1.0,  # bullish when change greater than 1%
              spt['price_change_pct'] < -1.0  # bearish
              ]
choices = ['bullish', 'bear']

spt['trend'] = np.select(conditions, choices, default='range')


# print(pivots.head())
print(spt.tail(5))
