from pathlib import Path
import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. File Path Resolution
folder = Path(__file__).resolve().parent.parent / '_8MKT_LABELS' / '_inputs'
sorted_pqt_files = sorted(folder.glob('*.parquet'))
pqt_files = [pqt.as_posix() for pqt in sorted_pqt_files]

# 2. DuckDB Query
conn = duckdb.connect()

# Passing python list directly to read_parquet in DuckDB
query = f"""--sql
    SELECT 
        open_time,
        open,
        high,
        low,
        close,
        volume,
        close_time
    FROM read_parquet($1)
    ORDER BY open_time ASC;
    """

df = conn.execute(query)
# conn.close()

# Convert Unix timestamp (ms) to Datetime
df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')

# Ensure numeric types for Plotly
cols_to_numeric = ['open', 'high', 'low', 'close', 'volume']
df[cols_to_numeric] = df[cols_to_numeric].apply(pd.to_numeric)


# 3. Plotly Candlestick & Volume Chart
# Create a 2-row layout (Row 1: Price Candlesticks, Row 2: Volume Bars)
fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.03,
    subplot_titles=('Price Action', 'Volume'),
    row_width=[0.2, 0.8],  # 80% height for price, 20% height for volume
)

# Add Candlesticks
fig.add_trace(
    go.Candlestick(
        x=df['open_time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='OHLC',
        increasing_line_color='#26a69a',  # TradingView green
        decreasing_line_color='#ef5350',  # TradingView red
    ),
    row=1,
    col=1,
)

# Add Volume Bars
fig.add_trace(
    go.Bar(
        x=df['open_time'],
        y=df['volume'],
        name='Volume',
        marker_color='rgba(100, 110, 120, 0.5)',  # Muted grey
    ),
    row=2,
    col=1,
)

# Layout adjustments for a clean, interactive aesthetic
fig.update_layout(
    title='Binance Daily Klines (Jan 2026 - Jun 2026)',
    template='plotly_dark',  # Dark mode for easier visual analysis
    xaxis_rangeslider_visible=False,  # Disables default bottom range slider
    hovermode='x unified',  # Show OHLC and Volume together on hover
    height=800,  # Chart height in pixels
    showlegend=False,
)

# Hide non-trading gaps (optional for crypto, but good practice for formatting)
fig.update_xaxes(type='category', row=2, col=1)

# Render in browser
fig.show()
