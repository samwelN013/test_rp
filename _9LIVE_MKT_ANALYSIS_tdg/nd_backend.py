print("WYNAN technologies")

import pandas as pd
import numpy as np
import duckdb
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px
from binance.client import Client
from datetime import datetime, timezone
import time
#color columns
from rich.console import Console
from rich.table import Table
# ------------- configure dataframe printing layout 
pd.set_option('display.expand_frame_repr', False)
pd.set_option('display.max_columns', None)
# TO FORMAT COLUMNS to display data not in scientific format
pd.set_option('display.float_format', lambda x: f'{x:,.2f}')

# FILE PATH and SQL QUERY

# Current UTC date string matching Binance file naming
today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
# file path
SYMBOL = "ADAUSDT"

# folder = Path.cwd() /"_inputs"/"binance_aggts"/f"{SYMBOL}_current_data"
folder = Path(__file__).resolve().parent/"_inputs"/"binance_aggts"/f"{SYMBOL}_current_data"
print(folder.exists())

# access the files
all_files = sorted(folder.glob("*.parquet"))

# 1.FOR THE DAILY TIMEFRAME , table queries and loads daily_files:  Daily Macro Analysis: All completed daily files (excludes today's _Hxx files)
daily_files = [f.as_posix() for f in all_files if "_H" not in f.name]

# 2. FOR THE HOURLY TIMEFRAME , table queries and loads hourly_files:  Hourly Entry Analysis: Last 2 completed daily files + all available hourly files today
daily_files = [f.as_posix() for f in all_files if "_H" not in f.name]
hourly_shards = [f.as_posix() for f in all_files if "_H" in f.name]
hourly_files = daily_files[-2:] + hourly_shards

# AGGTRADES RAW TABLE =============================================

# LOAD  aggregated DATA TO dataframe with  DUCKDB
conn = duckdb.connect(database=":memory:")
# Select your desired timeframe here: '1 Day', '1 Hour', '5 Minutes', '4 Hours', etc.
timeframe = '1 Day'

qry = f"""--sql
SELECT
    time_bucket(INTERVAL '{timeframe}', epoch_ms(CAST(transact_time AS BIGINT))) AS open_time,
    arg_min(price, transact_time) AS open,
    max(price) AS high,
    min(price) AS low,
    arg_max(price, transact_time) AS close,
    time_bucket(INTERVAL '{timeframe}', epoch_ms(CAST(transact_time AS BIGINT))) + INTERVAL '{timeframe}' - INTERVAL '1 millisecond' AS close_time,
    sum(CASE WHEN is_buyer_maker = FALSE THEN (price * quantity) ELSE 0.0 END) AS buyVol_usdt,
    sum(CASE WHEN is_buyer_maker = TRUE  THEN (price * quantity) ELSE 0.0 END) AS sellVol_usdt
FROM read_parquet({daily_files})
GROUP BY 1
ORDER BY open_time ASC;
"""
df = conn.execute(qry).df()
conn.close()

# RAW market MEGA METRICS TABLE  PART 1 (14 columns sofar)

# derived columns  ------------------------------------- PERCENTAGES
df['totalVol_usdt'] = (df['buyVol_usdt'] + df['sellVol_usdt']).round(3)
# ----------------------------------------------
df['volume_ma20'] = df['totalVol_usdt'].rolling(window=20).mean()
#-----------------------------------------------
df['delta'] = (df['buyVol_usdt'] - df['sellVol_usdt']).round(3)

df['prc_change_window'] = ((
    df['close']-df['open'])/df['open'])*100

# df['full__pct_change']
# Candle direction condition (True for Bullish, False for Bearish)
is_bull = df['close'] >= df['open']
df['full_pct_change'] = np.where(
    is_bull,
    ((df['high'] - df['low']) / df['low']) * 100,
    ((df['low'] - df['high']) / df['high']) * 100
)
# price change ma20
absolute_pct_change =df['prc_change_window'].abs()

df['prc_change_ma20']= absolute_pct_change.rolling(20).mean()
# relative price change
df["rel_prc_change"] = absolute_pct_change / df['prc_change_ma20']

# Range as a percentage of the Open price
df['bar_volatility'] = ((df['high'] - df['low']) / df['open']) * 100

# core derived columns
# df['s_delta_pct'] = (df['delta']/notional_ma)*100

df['s_delta_pct'] = (df['delta']/df['volume_ma20'])*100

delta_abs = df['delta'].abs()
delta_abs_mean = df['delta'].abs().rolling(20).mean()
delta_std_abs = df['delta'].abs().rolling(20).std()
#option 1
df["standzd_delta"] = df['delta']/delta_abs_mean
#option 2
df["standzd_delta_dev_zscore"] = ((df['delta'] - delta_abs_mean)/delta_std_abs).abs()

# PART 2 ()  ADDING THE PIVOT POINTS of candle wicks TO THE TABLE ==================

left_len =10
right_len = 10
window_size = left_len + right_len + 1
#Rolling max/min centered on the target candle
rolling_max = df['high'].rolling(window= window_size, center=True).max()
rolling_min = df['low'].rolling(window= window_size, center= True).min()
# Indentify pivot points (hing must equal max of the window and low must equal min of the window )
df['pivot_high'] = df['high'].where(df['high']==rolling_max, None)
df['pivot_low'] = df['low'].where(df['low']==rolling_min, None)
# Combined column showing the price level at the swing point, or None otherwise
df['swing_point_wcks'] = df['pivot_high'].combine_first(df['pivot_low'])

#-------------------------------------------------------------------------------
#  Structural Pivot Detection with Body-Level Price Extraction
df['pivot_h_raw'] = df['high'].where(df['high'] == rolling_max, None)
df['pivot_l_raw'] = df['low'].where(df['low'] == rolling_min, None)
#  Extract true Body Top and Body Bottom levels across all candles
body_top = df[['open', 'close']].max(axis=1)
body_bottom = df[['open', 'close']].min(axis=1)
#  Read off Body Top/Bottom ONLY on candles identified as structural pivots
df['pivot_high_bdy'] = np.where(df['pivot_h_raw'].notna(), body_top, None)
df['pivot_low_bdy'] = np.where(df['pivot_l_raw'].notna(), body_bottom, None)
#  Combine into final swing point column (body-based price level)
df['swing_point_bdy'] = df['pivot_high_bdy'].combine_first(df['pivot_low_bdy'])
# Clean up temporary raw detector columns if desired
df = df.drop(columns=['pivot_h_raw', 'pivot_l_raw'])
#-------------------------------------------------------------------------------

# PART 3  () computing internal metrics of SWING MOVES 

# 1. Create a dynamic segment group ID for each swing move
df['swing_group_wck'] = df['swing_point_wcks'].notna().cumsum()
df['swing_group_wck'] = df['swing_group_wck'].shift(1, fill_value=0)
# 2. Cumulative volume and delta metrics within each swing segment
df['cum_buyVol_internal'] = df.groupby('swing_group_wck')['buyVol_usdt'].cumsum()
df['cum_sellVol_internal'] = df.groupby('swing_group_wck')['sellVol_usdt'].cumsum()
df['cum_totalVol_internal'] = df.groupby('swing_group_wck')['totalVol_usdt'].cumsum()
df['cum_delta_internal'] = df.groupby('swing_group_wck')['delta'].cumsum()


#  detailed column ::: PERCENTAGE CHANGE FROM SWING PIVOT POINT

# 1. Generate Swing Groups strictly based on body pivot occurrences
df['is_pivot'] = df['swing_point_bdy'].notna() #has bo0lean results true/false
# Group 0 = pre-pivot candles. Group 1 = first swing move, Group 2 = second swing move, etc.
df['swing_group_bdy'] = df['is_pivot'].cumsum()
# 2. Extract the TRUE starting anchor price for each group
# ***
# For any group > 0, the first row of that group contains the pivot candle itself,
# so transform('first') picks up that exact pivot price!
df['pivot_anchor'] = df.groupby('swing_group_bdy')['swing_point_bdy'].transform('first')
# -------
# 3. Handle Group 0 (Synthetic Baseline) without variable collisions
first_candle_open = float(df['open'].iloc[0])
first_candle_close = float(df['close'].iloc[0])
# Safe extraction of body top / body bottom using Series min/max (avoids builtin max/min collision)
body_top_first = max([first_candle_open, first_candle_close])
body_bottom_first = min([first_candle_open, first_candle_close])
# Get the first valid pivot price in the whole dataset
valid_anchors = df['pivot_anchor'].dropna()

if len(valid_anchors) > 0:
    first_valid_pivot = valid_anchors.iloc[0]
    # If first pivot is above 1st candle open -> Bullish move expected -> anchor to body_bottom
    # If first pivot is below 1st candle open -> Bearish move expected -> anchor to body_top
    pre_swing_start_price = body_bottom_first if first_valid_pivot > first_candle_open else body_top_first
else:
    pre_swing_start_price = first_candle_open
# Fill Group 0's NaN with the pre-pivot synthetic price
df['swing_start_price'] = df['pivot_anchor'].fillna(pre_swing_start_price)
# ---------------------------------------------------------
# 4. Calculate Price Percentage change from swing Pivot Point
# ---------------------------------------------------------
df['pct_change_from_pivot'] = ((df['close'] - df['swing_start_price']) / df['swing_start_price']) * 100

# Clean up temporary detection columns
df = df.drop(columns=['is_pivot', 'pivot_anchor'])

#===========================================================
df['cum_delta_all'] = df['delta'].cumsum()
# df = df.drop(columns=['cum_delta_all'])

# MORE COLUMNS TO DROP
df = df.drop(columns=['swing_group_wck', 'swing_group_bdy','swing_start_price'])

# PART 4 () - OTHER 2 analysis columns 

#-----------------------#  POTENTIAL PIVOT COLUMN ---------

# Calculate rolling 10-bar high and low of the PREVIOUS 10 candles (excluding current candle)
prev_left_max = df['high'].shift(1).rolling(window=left_len).max()
prev_left_min = df['low'].shift(1).rolling(window=left_len).min()
# Conditions for potential pivots
is_potential_short = df['high'] > prev_left_max  # New 10-bar high (Potential 'SHORT')
is_potential_long = df['low'] < prev_left_min   # New 10-bar low (Potential 'LONG')
# Create df['potential_pivot'] column
# Labels: 'S' for potential short pivot, 'L' for potential long pivot, None otherwise
df['potential_pivot'] = np.select([is_potential_short, is_potential_long], ['S', 'L'], default=None)

#-----------------------#  ACTUAL_PIVOT COLUMN---------------------

# 1. Label confirmed pivot highs ('S') and confirmed pivot lows ('L')
df['actual_pivot_h'] = np.where(df['pivot_high'].notna(), 'S', None)
df['actual_pivot_l'] = np.where(df['pivot_low'].notna(), 'L', None)

# 2. Combine into a single df['actual_pivot'] column
df['actual_pivot'] = df['actual_pivot_h'].combine_first(df['actual_pivot_l'])

# Optional: Drop the intermediate temporary columns
df = df.drop(columns=['actual_pivot_h', 'actual_pivot_l'])

# ==================================================================================
     # RELATIVE VOLUME COLUMN
# 1. Calculate the 20-period Simple Moving Average (SMA) of candle volume

# 2. Compute Relative Volume (RVOL)
df['rvol'] = df['totalVol_usdt'] / df['volume_ma20']

#===============================================================
atr_period = 14

# 1. Calculate Previous Close
prev_close = df['close'].shift(1)

# 2. Compute the 3 True Range components
tr1 = df['high'] - df['low']
tr2 = (df['high'] - prev_close).abs()
tr3 = (df['low'] - prev_close).abs()

# 3. Calculate True Range (TR) as the maximum of the 3 components
df['TR'] = np.maximum(tr1, np.maximum(tr2, tr3))

# 4. Compute 14-period Average True Range (ATR)
# Option A: Standard Simple Moving Average (SMA) - standard and fastest
df['ATR'] = df['TR'].rolling(window=atr_period).mean()

# Clean up temporary TR column if desired
df = df.drop(columns=['TR'])

# --------------------- LONGSTOPLOSS & SHORTSTOPLOSS ----------
atr_multiplier = 1.50
# === Stop Levels (anchored from OPEN) ===
df['longstop']= (df['open']-(df['ATR']* atr_multiplier))
df['shortstop']= (df['open']+(df['ATR']* atr_multiplier))

#====================================================================
# Get individual ROWS and COLUMNS counts
rows = df.shape[0]
columns = df.shape[1]
print(f"Rows: {rows}, Columns: {columns} \n")

# BEFORE (left side of the pivot point)  --- for  CURRENT MARKET STATE- -- MARKET BEHAVIOR COLUMNS  : A ) PRICE
bf= df[df['rvol'].notna()].reset_index(drop=True)
bf = bf.sort_values("open_time").reset_index(drop=True)

close_bh = bf["close"]

#------------ PRICE BEHAVIOR MODELLING
w_sz =3 # window size

# P1 — Return : tells  DIRECTION and MAGNITUDE.
# bf["price_returnZ_3"] = (close_bh / close_bh.shift(w_sz) - 1)* 100 
bf["price_return_3"] = close_bh.pct_change(w_sz) * 100 
#P2 —  velocity - rate of change of price
bf["price_velocity"] = bf["price_return_3"] / w_sz
#P3 - relative price change 
# bf["rel_price_pct_change"] =bf["rel_prc_change"].shift(1)  # standardizes price changes
bf["rel_price_pct_change"] =bf["rel_prc_change"]

# P4 - bar_volatility_bh
bf["bar_volatility_bh"] = bf["bar_volatility"]
bf["potential_pivot_bh"]  = bf["potential_pivot"]
bf["actual_pivot_bh"]     = bf["actual_pivot"] 
bf["swing_point_wcks_bh"]= bf["swing_point_wcks"]
bf["close_bh"]            = bf["close"]    
bf["prc_change_window_bh"]= bf["prc_change_window"]

# def add_directional_features(bf, col, prefix, W=5):
def add_directional_features(bf=bf, col="prc_change_window_bh", prefix="price", W=3):
    x = bf[col]

    # Positive and negative magnitudes
    bull = x.clip(lower=0)
    bear = (-x).clip(lower=0)

    # Directional persistence: fraction of candles in each direction
    bull_count = x.gt(0).rolling(W, min_periods=W).sum()
    bear_count = x.lt(0).rolling(W, min_periods=W).sum()

    bf[f"{prefix}_bull_persistence"] = (bull_count / W)*100
    bf[f"{prefix}_bear_persistence"] = (bear_count / W)*100

    # Conditional intensity: mean magnitude when that direction occurs
    bull_sum = bull.rolling(W, min_periods=W).sum()
    bear_sum = bear.rolling(W, min_periods=W).sum()

    bf[f"{prefix}_bull_intensity"] = (
        bull_sum / bull_count.replace(0, np.nan)
    )

    bf[f"{prefix}_bear_intensity"] = (
        bear_sum / bear_count.replace(0, np.nan)
    )

    # Directional activity: combines frequency and magnitude
    bf[f"{prefix}_bull_activity"] = bull.rolling(
        W, min_periods=W
    ).mean()

    bf[f"{prefix}_bear_activity"] = bear.rolling(
        W, min_periods=W
    ).mean()

add_directional_features()
# ================================================================================

#BULL price activity dominance percentage
bf["price_bull_dominance"] = (bf["price_bull_activity"] / ( bf["price_bear_activity"] + bf["price_bull_activity"]))* 100
bf["price_bear_dominance"] = (bf["price_bear_activity"] / ( bf["price_bear_activity"] + bf["price_bull_activity"]))* 100

# B ) VOLUME BEHAVIOUR ANALYSIS : the numeric language interpretation ( 3 suggested columns) $ ( 7 previous columns)
bf["delta_bh"] = bf["delta"]
bf["totalVol_bh"]= bf["totalVol_usdt"]

# v1 — relative volume
bf["rvol_bh"]   = bf["rvol"]
# V2 — Volume / liquidity / rvol persistence
win =3
bf["rvol_persistence"] = (
    bf["rvol_bh"]
    .ge(1.0)
    .rolling(win, min_periods=win)
    .mean()
)*100

bf["rvol_intensity"] = (
    bf["rvol_bh"]
    .rolling(win, min_periods=win)
    .mean()
)

# C ) DELTA BEHAVIOUR ANALYSIS : the numeric language interpretation ( 5 suggested columns) $ ( 18 previous columns)

delta_bh = bf["delta"]
bf["delta_bh"] = bf["delta"]
bf["totalVol_bh"]= bf["totalVol_usdt"]

bf["rvol_bh"]   = bf["rvol"]
bf["s_delta_pct_bh"] =bf["s_delta_pct"]
# D1 — Delta imbalance
bf["delta_imbalance_pct_bh"] = (bf["delta_bh"] / bf["totalVol_bh"])*100

#D2 Standardized delta
#option 1
bf["standzd_delta_bh"] = bf["standzd_delta"]
#option 2
bf["standzd_delta_dev_bh"] = bf["standzd_delta_dev_zscore"]

# def add_directional_features(bf, col, prefix, W=5):
def add_directional_features_delta(bf=bf, col="standzd_delta_bh", prefix="std_delta", W=3):
    x = bf[col]

    # Positive and negative magnitudes
    bull = x.clip(lower=0)
    bear = (-x).clip(lower=0)

    # Directional activity: combines frequency and magnitude
    bf[f"{prefix}_bull_activity"] = bull.rolling(
        W, min_periods=W
    ).mean()

    bf[f"{prefix}_bear_activity"] = bear.rolling(
        W, min_periods=W
    ).mean()

add_directional_features_delta()
#D5
#BULL standrd delta activity dominance percentage
bf["std_delta_bull_dominance"] = (bf["std_delta_bull_activity"] / ( bf["std_delta_bear_activity"] + bf["std_delta_bull_activity"]))* 100
bf["std_delta_bear_dominance"] = (bf["std_delta_bear_activity"] / ( bf["std_delta_bear_activity"] + bf["std_delta_bull_activity"]))* 100
# delta_divergence
bf["delta_divergence"] = (bf["standzd_delta_bh"]  * bf["prc_change_window_bh"] < 0)

# D ) BUY_RATIO BEHAVIOUR ANALYSIS : the numeric language interpretation ( 3 suggested columns) $ ( 11 previous columns)

buyVol_bh = bf["buyVol_usdt"]
sellVol_bh = bf["sellVol_usdt"]
bf["totalVol_bh"]= bf["totalVol_usdt"]
# B1  : BR - buyratio
bf["buy_ratio_bh"] = (buyVol_bh / bf["totalVol_bh"])*100
# Rolling average aggressive-buy share
W = 3
bf["buy_pressure_persistence"] = (
    bf["buy_ratio_bh"]
    .rolling(W, min_periods=W)
    .mean()
)
# B2  : SR - sellratio
bf["sell_ratio_bh"] = (sellVol_bh / bf["totalVol_bh"])*100
# B4
bf["sell_pressure_persistence"] = (
    bf["sell_ratio_bh"]
    .rolling(W, min_periods=W)
    .mean()
)

# E ) CANDLE SIZE THESIS
bf["open_bh"] = bf["open"]
bf["low_bh"] = bf["low"]
bf["high_bh"] = bf["high"]
# Total candle range
candle_range = bf["high_bh"] - bf["low_bh"]
# candle_range = candle_range.replace(0, np.nan)

# Candle anatomy as percentages of the total range
bf["upper_wick_pct"] = (
    (bf["high_bh"] - bf[["open_bh", "close_bh"]].max(axis=1))
    / candle_range
) * 100

bf["body_pct"] = (
    (bf["close_bh"] - bf["open_bh"]).abs()
    / candle_range
) * 100

bf["lower_wick_pct"] = (
    (bf[["open_bh", "close_bh"]].min(axis=1) - bf["low_bh"])
    / candle_range
) * 100

# Avoid division by zero for candles with no price range
bf.loc[candle_range == 0, [
    "upper_wick_pct", "body_pct", "lower_wick_pct"
]] = np.nan
# -----------------------------------------------

# RIGHT CANDLES RETURNS === OUTCOME ANALYSIS : To the pivot

# -------------- bytheway coin loaded remainder ------------------
print(f"                  Loaded Symbol       :            {SYMBOL}")
# ------------------------------------------------------------

# Identify confirmed pivot candles
pivot_mask = bf["swing_point_wcks"].notna()
pivot_positions = np.flatnonzero(pivot_mask.to_numpy())

# Initialize outcome columns
bf["return_to_pivot_pct"] = np.nan
bf["return_price_velocity"] = np.nan
bf["bars_to_pivot"] = np.nan

opens = bf["open"].to_numpy(dtype=float)
closes = bf["close"].to_numpy(dtype=float)

# Use the CLOSE of each confirmed pivot candle
pivot_close_prices = closes[pivot_positions]

for i in range(len(bf)):

    # Find the nearest confirmed pivot strictly after candle i
    next_idx = np.searchsorted(pivot_positions, i, side="right")

    if next_idx >= len(pivot_positions):
        continue

    pivot_pos = pivot_positions[next_idx]

    start_price = opens[i]
    end_price = pivot_close_prices[next_idx]
    bars = pivot_pos - i

    if not np.isfinite(start_price) or start_price <= 0:
        continue

    # 1. Percentage return from current candle OPEN to pivot candle CLOSE
    return_pct = ((end_price - start_price) / start_price) * 100

    # 2. Average percentage return per bar
    velocity = return_pct / bars if bars > 0 else np.nan

    # 3. Number of bars until the next confirmed pivot
    bf.iloc[i, bf.columns.get_loc("return_to_pivot_pct")] = return_pct
    bf.iloc[i, bf.columns.get_loc("return_price_velocity")] = velocity
    bf.iloc[i, bf.columns.get_loc("bars_to_pivot")] = bars


fwd_cols = [
    # ORIGINAL COLUMNS
    "open_time",

    # necessary COLUMNS
    "potential_pivot_bh",
    "actual_pivot_bh", 
    "swing_point_wcks_bh",
    # "close_bh",

    #CANDLE
    # "upper_wick_pct",
    # "body_pct",
    # "lower_wick_pct",

        
    
    # "price_bull_activity",
    # "price_bear_activity",
    "price_bull_dominance",
    "price_bear_dominance",

    "price_bull_persistence",
    # "price_bull_intensity",
    "price_bear_persistence",    
    # "price_bear_intensity",

    # PRICE COLUMNS
     
    # "price_return_3",  
    # "price_velocity", 
    # VOLUME COLUMNS
   
    "rvol_persistence",
    "rvol_intensity",
    # DELTA COLUMNS 
    "bar_volatility_bh",
    "rvol_bh", 
    # "rvol", 
    "delta_imbalance_pct_bh",
    # "standzd_delta_bh",
    "delta_divergence",
    "prc_change_window_bh",
    "rel_price_pct_change",
    "return_to_pivot_pct",
    
    # "std_delta_bull_activity",
    # "std_delta_bear_activity",
    "std_delta_bull_dominance",
    "std_delta_bear_dominance",

    # "standzd_delta_dev_bh",

    # BUY-RATIO COLUMNS 
    "buy_ratio_bh",
    "buy_pressure_persistence",
    "sell_ratio_bh",
    "sell_pressure_persistence",
    # Machine Learning COLUMNS
    "target_pvt_bull",
    # FORWARD RETURN COLUMNS
    "bars_to_pivot",
    
    # "return_price_velocity",    
]

# CSS / HTML FUNCTION TO FORMAT THE TABLE

def style_trading_df(
    df,
    cols=None,
    start=0,
    end=50,
    max_height="700px",
    # Color settings -----------------------------------------------
    bool_cols=None,         # <--- 1. ADD THIS PARAMETER (dict: {"col_name": ("#2ecc71", "#e74c3c")})
    static_color_cols=None, # dict: {"col_name": "yellow"}
    pos_neg_cols=None,      # list of cols for green/red based on +/-
    threshold_cols=None,    # dict: {"col_name": (50, "green", "red")}
    bg_highlight_cols=None, # list or dict of cols for background tint
    precision_map=None      # dict: {"col_name": 2}
):
    """
    Renders an HTML-styled DataFrame in Jupyter with frozen headers, 
    frozen 'open_time' column, conditional colors, centered text, and signal row highlighting.
    """
    # 1. Slice rows cleanly (e.g., df[30:70])
    sub_df = df.iloc[start:end].copy()
    
    # Select columns if specified
    if cols is not None:
        sub_df = sub_df[[c for c in cols if c in sub_df.columns]]
        
    # Set 'open_time' as index if present so it locks on horizontal scroll
    has_open_time = "open_time" in sub_df.columns
    if has_open_time:
        sub_df = sub_df.set_index("open_time")
        sub_df.index.name = None  # FIX 1: Removes multi-level index header split

    # Defaults for column lists if not provided   ---------------------------------------------------------
    if static_color_cols is None:
        static_color_cols = {
            "rel_price_pct_change": "#a692be",
            "rvol_bh": "#8d9199",
            "upper_wick_pct": "#8d9199",
            "body_pct": "#4e7a66",
            "lower_wick_pct": "#8d9199",

            "price_bull_persistence": "#a39f50",
            "price_bull_intensity": "#8d9199",
            "price_bear_persistence": "#a39f50",
            "price_bear_intensity": "#8d9199",
            }
        
    if pos_neg_cols is None:
        pos_neg_cols = [
            "prc_change_window_bh", "price_return_3", "price_velocity", 
            "standzd_delta_bh", "delta_imbalance_pct_bh", "return_to_pivot_pct", 
            "return_price_velocity"
        ]
        
    if threshold_cols is None:
        threshold_cols = {
                           "buy_ratio_bh": (50.0, "#2ecc71", "#e74c3c"),
                           "sell_ratio_bh": (50.0, "#cb7de3" , "#3d8eeb"),
                           
                        } 
        # sell ratio bh colors ------------------ #bf26ed

    # Default boolean columns configuration
    if bool_cols is None:
        bool_cols = {
            "delta_divergence": ("#c7d830", "#1c85e7"),  # True -> Green, False -> Red
            # "volume_spike": ("#2ecc71", "#e74c3c"),    # Add more boolean columns here easily!
        }    
        
    if bg_highlight_cols is None:
        bg_highlight_cols = ["return_to_pivot_pct", "return_price_velocity", "bars_to_pivot"] #,"prc_change_window"

    def color_boolean(val, true_color, false_color):
        if pd.isna(val): return ''
        if str(val).strip().lower() in ['true', '1', '1.0']:
            return f'color: {true_color}; font-weight: normal;'
        if str(val).strip().lower() in ['false', '0', '0.0']:
            return f'color: {false_color}; font-weight: normal;'
        return ''
    
    # 2. Row Highlighting Logic (Pivot Signals)
    def highlight_signal_rows(row):
        styles = [''] * len(row)
        
        swing = row.get("swing_point_wcks_bh", np.nan) # ------------------------ swings and pivots
        pot_piv = str(row.get("potential_pivot_bh", ""))
        act_piv = str(row.get("actual_pivot_bh", ""))
        
        bg_color = None
        
        # Rule a: swing_point_wcks_bh is NaN and potential_pivot_bh exists  ------------------------------
        if pd.isna(swing) or swing == "":
            if pot_piv == "S":          # in ["S", "L"]:
                bg_color = "background-color: #222847; color: white;" # pale blue
            elif pot_piv == "L":
                bg_color = "background-color: #3d3a12; color: white;" # dark yellow           
                
        # Rule b: swing_point_wcks_bh is not-NaN
        else:
            if act_piv == "S":
                bg_color = "background-color: #6a396b; color: white;" # Light purple
            elif act_piv == "L":
                bg_color = "background-color: #396145; color: white;"  # Light green   
                
        if bg_color:
            return [bg_color] * len(row)
        return styles

    # 3. Value-based Cell Styling Functions
    def color_pos_neg(val):
        if pd.isna(val): return ''
        if val > 0: return 'color: #2ecc71; font-weight: normal;'
        if val < 0: return 'color: #e74c3c; font-weight: normal;'
        return ''

    def color_threshold(val, thresh, high_color, low_color):
        if pd.isna(val): return ''
        if val > thresh: return f'color: {high_color}; font-weight: normal;'
        if val < thresh: return f'color: {low_color}; font-weight: normal;'
        return ''

    # Start Styler pipeline
    styler = sub_df.style

    # Apply row highlighting
    styler = styler.apply(highlight_signal_rows, axis=1)

    # Apply static column font colors
    for col, color in static_color_cols.items():
        if col in sub_df.columns:
            styler = styler.map(lambda v, c=color: f'color: {c}; font-weight: normal;', subset=[col])

    # Apply positive/negative green/red font colors
    valid_pos_neg = [c for c in pos_neg_cols if c in sub_df.columns]
    if valid_pos_neg:
        styler = styler.map(color_pos_neg, subset=valid_pos_neg)

    # Apply threshold coloring
    for col, (thresh, high_c, low_c) in threshold_cols.items():
        if col in sub_df.columns:
            styler = styler.map(
                lambda v, t=thresh, h=high_c, l=low_c: color_threshold(v, t, h, l), 
                subset=[col]
            )

    # Apply boolean coloring (True -> Green, False -> Red)
    for col, (true_c, false_c) in bool_cols.items():
        if col in sub_df.columns:
            styler = styler.map(
                lambda v, tc=true_c, fc=false_c: color_boolean(v, tc, fc),
                subset=[col]
            )

    # Apply background highlight to column groups
    valid_bg_cols = [c for c in bg_highlight_cols if c in sub_df.columns]
    if valid_bg_cols:
        styler = styler.map(
            lambda v: 'background-color: #2e1342;',
            subset=valid_bg_cols
        )

    # 4. Control Decimal Precision
    default_format = {
        "swing_point_wcks_bh": "{:.2f}",

        "upper_wick_pct":"{:.0f} %",
        "body_pct":"{:.0f} %",
        "lower_wick_pct":"{:.0f} %",

        "close_bh": "{:.2f}",
        "bar_volatility_bh":"{:.2f} %",

        "prc_change_window_bh": "{:+.2f} %",
        "price_bull_persistence":"{:.0f} %",
        "price_bull_intensity": "{:.3f}",
        "price_bear_persistence":"{:.0f} %",
        "price_bear_intensity" :"{:.3f}",
        "price_bull_activity" :"{:.3f}",
        "price_bear_activity" :"{:.3f}",
        "price_bull_dominance":"{:.0f} %",
        "price_bear_dominance":"{:.0f} %",

        "rel_price_pct_change": "{:.2f}",
        "price_return_3": "{:.2f} %",
        "price_velocity": "{:+.2f} %",

        "rvol_bh": "{:.2f}",
        "rvol_persistence":"{:.0f} %",
        "rvol_intensity":"{:.2f}",

        "standzd_delta_bh": "{:.2f}",
        "std_delta_bull_dominance":"{:.0f} %",
        "std_delta_bear_dominance":"{:.0f} %",
        "std_delta_bull_activity":"{:.2f}",
        "std_delta_bear_activity":"{:.2f}",
        
        "delta_imbalance_pct_bh": "{:.2f} %",
        "buy_ratio_bh": "{:.2f}",
        "buy_pressure_persistence": "{:.2f}",
        "sell_ratio_bh": "{:.2f}",
        "sell_pressure_persistence": "{:.2f}",

        "return_to_pivot_pct": "{:.2f} %",
        "return_price_velocity": "{:.2f} %",
        "bars_to_pivot": "{:.0f}"
    }
      
    if precision_map:
        for col, dec in precision_map.items():
            default_format[col] = f"{{:.{dec}f}}"
            
    active_format = {k: v for k, v in default_format.items() if k in sub_df.columns}
    styler = styler.format(active_format, na_rep="-")

    # 5. CSS & Sticky Positioning
    table_css = [
        {'selector': '', 'props': [
            ('max-height', max_height), 
            ('overflow', 'auto'), 
            ('display', 'block')
        ]},
        # FIX 2: Data cells have fixed height; headers (th) fit text naturally
        {'selector': 'td', 'props': [
            ('height', '16px'), 
            ('min-height', '16px'), 
            ('max-height', '16px'),
            ('padding', '4px 8px'),
            ('white-space', 'nowrap'),
            ('text-align', 'center !important')
        ]},
        {'selector': 'th', 'props': [
            ('padding', '6px 8px'),
            ('white-space', 'nowrap'),
            ('text-align', 'center !important')
        ]},
        # Header Sticky Fix
        {'selector': 'th.col_heading', 'props': [
            ('background-color', "#423a42 !important"), 
            ('color', "#ffffffbe !important"), 
            ('position', 'sticky !important'),
            ('top', '0 !important'),
            ('z-index', '3 !important')
        ]},
        # Index Column (open_time values) Sticky Fix
        {'selector': 'th.row_heading', 'props': [
            ('background-color', '#1e1e1e !important'), 
            ('color', "#d6df58d6 !important"), 
            ('position', 'sticky !important'),
            ('left', '0 !important'),
            ('z-index', '2 !important')
        ]},
        # Top-Left corner intersection
        {'selector': 'th.blank', 'props': [
            ('background-color', "#423a42 !important"), 
            ('position', 'sticky !important'),
            ('top', '0 !important'),
            ('left', '0 !important'),
            ('z-index', '4 !important')
        ]}
    ]

    styler = (
        styler
        .set_sticky(axis=0)  # Freeze top header row
        .set_sticky(axis=1)  # Freeze leftmost index column
        .set_table_styles(table_css)
    )

    return styler

style_trading_df(bf, cols=fwd_cols, start=0, end=1000)

#============================================================

# print(bf[fwd_cols][:100].to_string())
# print(bf[fwd_cols])
