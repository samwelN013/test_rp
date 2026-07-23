import pandas as pd
import duckdb
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px

# file path
folder = Path(__file__).resolve().parent.parent / \
    '_8MKT_LABELS' / '_inputs'/'dayly_klines'
# access the files
sorted_pqt_files = sorted(folder.glob('*parquet'))
# file list
pqt_file = [pqt.as_posix() for pqt in sorted_pqt_files]

# duckdb query for the data
conn = duckdb.connect()

query = f"""--sql
        select 
            --cast for ms to readeable time
            --epoch_ms(CAST(open_time as bigint)) as open_time,
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
# .dt.strftime("%Y-%m-%d %H:%M:%S")

# print(df.head())

# Ensure numeric types for Plotly
cols_to_numeric = ['open', 'high', 'low', 'close']
df[cols_to_numeric] = df[cols_to_numeric].apply(pd.to_numeric)
# THE CANDLE CHART

fig = go.Figure()
fig.add_trace(go.Candlestick(x=df['open_time'],
                             open=df['open'],
                             high=df['high'],
                             low=df['low'],
                             close=['close'],
                             name='OHLC',
                             increasing_line_color='#26a69a',
                             decreasing_line_color='#ef5350'))

fig.update_layout(title='2026 SOL day timeframe chart',
                  template='plotly_dark',
                  xaxis_rangeslider_visible=False,
                  hovermode='x unified',
                  showlegend=False,)

fig.show()
