from pathlib import Path
import duckdb
import pandas as pd
import plotly.graph_objects as go

# File path
folder = (
    Path(__file__).resolve().parent.parent
    / '_8MKT_LABELS'
    / '_inputs'
    / 'dayly_klines'
)
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

# DF for PIVOT POINTS ONLY
pv_df = df[df['swing_point'].notna()]

# print(pv_df.to_string())
# print(pv_df.tail())
# print(pv_df)
print(df.head())