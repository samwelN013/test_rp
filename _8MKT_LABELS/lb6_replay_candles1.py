import pandas as pd
import duckdb
from pathlib import Path
import plotly.graph_objects as go

# file path
folder = Path(__file__).resolve().parent.parent / '_8MKT_LABELS' / '_inputs' / 'dayly_klines'
# access the files
sorted_pqt_files = sorted(folder.glob('*parquet'))
# file list
pqt_file = [pqt.as_posix() for pqt in sorted_pqt_files]

# duckdb query for the data
conn = duckdb.connect()

query = f"""--sql
        select 
            open_time,
            open,
            high,
            low,
            close,
            close_time
        from read_parquet({pqt_file})    
        """

df = conn.execute(query).df()
conn.close()

df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

# Ensure numeric types for Plotly
cols_to_numeric = ['open', 'high', 'low', 'close']
df[cols_to_numeric] = df[cols_to_numeric].apply(pd.to_numeric)

# Sort values chronologically to ensure proper replay
df = df.sort_values('open_time').reset_index(drop=True)

# ---------------------------------------------------------
# 1. INITIAL STATE (Frame 0: Starting with the first candle)
# ---------------------------------------------------------
initial_df = df.iloc[:1]

fig = go.Figure(
    data=[
        go.Candlestick(
            x=initial_df['open_time'],
            open=initial_df['open'],
            high=initial_df['high'],
            low=initial_df['low'],
            close=initial_df['close'],
            name='OHLC',
            increasing_line_color='#26a69a',
            increasing_fillcolor='rgba(0, 0, 0, 0)',
            increasing_line_width=1,
            decreasing_line_color='#ef5350',
            decreasing_fillcolor='rgba(0, 0, 0, 0)',
            decreasing_line_width=1
        )
    ]
)

# ---------------------------------------------------------
# 2. GENERATE FRAMES (Each frame reveals one more candle)
# ---------------------------------------------------------
frames = []
for i in range(1, len(df) + 1):
    frame_df = df.iloc[:i]
    frames.append(
        go.Frame(
            data=[
                go.Candlestick(
                    x=frame_df['open_time'],
                    open=frame_df['open'],
                    high=frame_df['high'],
                    low=frame_df['low'],
                    close=frame_df['close']
                )
            ],
            name=str(i)  # Frame identifier
        )
    )

fig.frames = frames

# ---------------------------------------------------------
# 3. CONTROLS & SPEED CONFIGURATION
# ---------------------------------------------------------
# Set your frame duration in milliseconds (e.g., 200ms = 5 candles per second)
frame_duration = 100  # Adjust speed here! (Lower = Faster replay)

fig.update_layout(
    title='2026 SOL Day Timeframe Chart - Replay Mode',
    template='plotly_dark',
    xaxis_rangeslider_visible=False,
    hovermode='x unified',
    showlegend=False,
    height=600,
    
    # Fix the Axis Ranges so the chart doesn't rescale constantly while playing
    xaxis=dict(range=[df['open_time'].min(), df['open_time'].max()]),
    yaxis=dict(range=[df['low'].min() * 0.95, df['high'].max() * 1.05]),

    # Add Play and Pause Buttons
    updatemenus=[{
        "type": "buttons",
        "showactive": False,
        "direction": "left",
        "x": 0.05,
        "y": 1.15,
        "xanchor": "right",
        "yanchor": "top",
        "buttons": [
            {
                "label": "▶ Play",
                "method": "animate",
                "args": [
                    None,
                    {
                        "frame": {"duration": frame_duration, "redraw": True},
                        "fromcurrent": True,
                        "transition": {"duration": 0}  # Instant step to prevent lag
                    }
                ]
            },
            {
                "label": "⏸ Pause",
                "method": "animate",
                "args": [
                    [None],
                    {
                        "frame": {"duration": 0, "redraw": False},
                        "mode": "immediate",
                        "transition": {"duration": 0}
                    }
                ]
            }
        ]
    }]
)

fig.show()