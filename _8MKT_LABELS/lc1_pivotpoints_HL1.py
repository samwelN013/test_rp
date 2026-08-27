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

# ---------------------------------------------------------
# Plotting with Plotly (Optional Visual Check)
# ---------------------------------------------------------
fig = go.Figure()

fig = go.Figure(data=[
    go.Candlestick(
        x=df['open_time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Price',
        # bullish candles
        increasing_line_color='white',
        increasing_fillcolor='rgba(0, 0, 0, 0)',
        increasing_line_width=1,
        # bearish candles
        decreasing_line_color='#0677d4',
        decreasing_fillcolor='rgba(0, 0, 0, 0)',
        decreasing_line_width=1
    )
])
# -------------------------------------------- sma line
fig.add_trace(go.Scatter(x=df.open_time, y=df.sma25,
              mode='lines', line=dict(color='purple', width=1)))
# ---------------------------------------swing points line
fig.add_trace(go.Scatter(x=df.open_time, y=df.swing_point,
                         connectgaps=True,
              mode='lines', line=dict(color='green', width=1)))
# ----------------------------------------------
fig.update_layout(title='sol 2026 jan to june  day timeframe',
                  template='plotly_dark',
                  xaxis_rangeslider_visible=False,
                  hovermode='x unified',
                  showlegend=False,
                  height=600
                  )

# Add Pivot High Markers
pivot_highs = df.dropna(subset=['pivot_high'])
fig.add_trace(go.Scatter(
    x=pivot_highs['open_time'],
    y=pivot_highs['pivot_high'],
    mode='markers+text',
    marker=dict(symbol='triangle-down', size=10, color='red'),
    text=pivot_highs['pivot_high'],
    textposition='top center',
    name='Pivot High'
))

# Add Pivot Low Markers
pivot_lows = df.dropna(subset=['pivot_low'])
fig.add_trace(go.Scatter(
    x=pivot_lows['open_time'],
    y=pivot_lows['pivot_low'],
    mode='markers+text',
    marker=dict(symbol='triangle-up', size=10, color='green'),
    text=pivot_lows['pivot_low'],
    textposition='bottom center',
    name='Pivot Low'
))

fig.show()
