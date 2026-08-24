from pathlib import Path
import duckdb
import pandas as pd
import plotly.graph_objects as go

# 1. Load Data
folder = (
    Path(__file__).resolve().parent.parent
    / '_8MKT_LABELS'
    / '_inputs'
    / 'dayly_klines'
)
sorted_pqt_files = sorted(folder.glob('*.parquet'))
pqt_file = [pqt.as_posix() for pqt in sorted_pqt_files]

conn = duckdb.connect()
query = f"""
        SELECT open_time, open, high, low, close, close_time
        FROM read_parquet({pqt_file})
        ORDER BY open_time ASC
        """
df = conn.execute(query).df()
conn.close()

df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

cols_to_numeric = ['open', 'high', 'low', 'close']
df[cols_to_numeric] = df[cols_to_numeric].apply(pd.to_numeric)

# 2. Base Chart Setup
fig = go.Figure()

fig.add_trace(
    go.Candlestick(
        x=df['open_time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='OHLC',
        increasing_line_color='#26a69a',
        increasing_fillcolor='rgba(0, 0, 0, 0)',
        increasing_line_width=1,
        decreasing_line_color='#ef5350',
        decreasing_fillcolor='rgba(0, 0, 0, 0)',
        decreasing_line_width=1,
    )
)

# -------------------------------------------------------------
# 3. HIGHLIGHTING MARKET STATES (Shaded Background Regions)
# -------------------------------------------------------------

# Example: Strong Downtrend Region (e.g., Feb 2026)
fig.add_vrect(
    x0='2026-02-01',
    x1='2026-02-18',
    fillcolor='rgba(239, 83, 80, 0.12)',  # Light Red
    layer='below',
    line_width=0,
    annotation_text='Strong Downtrend',
    annotation_position='top left',
    annotation_font=dict(color='#ef5350', size=12),
)

# Example: Range / Consolidation Region
fig.add_vrect(
    x0='2026-03-01',
    x1='2026-04-15',
    fillcolor='rgba(100, 110, 120, 0.15)',  # Light Grey
    layer='below',
    line_width=0,
    annotation_text='Range / Compression',
    annotation_position='top left',
    annotation_font=dict(color='#cccccc', size=12),
)

# Example: Accumulation & Expansion Region (May 2026)
fig.add_vrect(
    x0='2026-05-01',
    x1='2026-05-25',
    fillcolor='rgba(38, 166, 154, 0.12)',  # Light Green
    layer='below',
    line_width=0,
    annotation_text='Accumulation & Expansion',
    annotation_position='top left',
    annotation_font=dict(color='#26a69a', size=12),
)

# -------------------------------------------------------------
# 4. HIGHLIGHTING MARKET EVENTS (Annotations & Circles)
# -------------------------------------------------------------

# Example: Labeling a Failed Breakout (Bull Trap)
fig.add_annotation(
    x='2026-01-28',
    y=df.loc[df['open_time'] == '2026-01-28', 'high'].values[0]
    if not df.loc[df['open_time'] == '2026-01-28'].empty
    else 150,
    text='Failed Breakout (Bull Trap)',
    showarrow=True,
    arrowhead=2,
    arrowcolor='#ef5350',
    arrowsize=1,
    arrowwidth=1.5,
    ax=0,
    ay=-40,
    font=dict(color='#ffffff', size=11),
    bgcolor='#ef5350',
    borderpad=4,
)

# Example: Labeling an Absorption Event
fig.add_annotation(
    x='2026-05-12',
    y=df.loc[df['open_time'] == '2026-05-12', 'low'].values[0]
    if not df.loc[df['open_time'] == '2026-05-12'].empty
    else 70,
    text='Absorption',
    showarrow=True,
    arrowhead=2,
    arrowcolor='#26a69a',
    arrowsize=1,
    arrowwidth=1.5,
    ax=0,
    ay=40,
    font=dict(color='#ffffff', size=11),
    bgcolor='#26a69a',
    borderpad=4,
)

# Example: Drawing a Circle around an Event
fig.add_shape(
    type='circle',
    xref='x',
    yref='y',
    x0='2026-05-10',
    y0=75,
    x1='2026-05-14',
    y1=85,
    line=dict(color='#ffb74d', width=2),
)

# 5. Final Chart Layout
fig.update_layout(
    title='2026 SOL Daily Timeframe — Market Event Annotations',
    template='plotly_dark',
    xaxis_rangeslider_visible=False,
    hovermode='x unified',
    showlegend=False,
    height=750,
)

fig.show()