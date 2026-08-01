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

# Ensure numeric types for Plotly
cols_to_numeric = ['open', 'high', 'low', 'close']
df[cols_to_numeric] = df[cols_to_numeric].apply(pd.to_numeric)

# THE CANDLE CHART (Price Only)

# THE CANDLE CHART (TradingView Style: Hollow Bodies, 1px Outlines & Wicks)
fig = go.Figure()

fig.add_trace(
    go.Candlestick(
        x=df['open_time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='OHLC',
        # --- Bullish Candles (Increasing) ---
        increasing_fillcolor='rgba(0, 0, 0, 0)',  # Hollow / Transparent body
        increasing_line_color='#26a69a',          # TradingView Green border & wick
        increasing_line_width=1,                  # Sharp 1px border/wick thickness
        
        # --- Bearish Candles (Decreasing) ---
        decreasing_fillcolor='rgba(0, 0, 0, 0)',  # Hollow / Transparent body
        decreasing_line_color='#ef5350',          # TradingView Red border & wick
        decreasing_line_width=1,                  # Sharp 1px border/wick thickness
    )
)

fig.update_layout(
    title='2026 SOL day timeframe chart',
    template='plotly_dark',
    xaxis_rangeslider_visible=False,
    hovermode='x unified',
    showlegend=False,
    height=700,
)

fig.show()