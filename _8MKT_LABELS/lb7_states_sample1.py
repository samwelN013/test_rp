from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# File path definition
folder = (
    Path(__file__).resolve().parent.parent
    / "_8MKT_LABELS"
    / "_inputs"
    / "dayly_klines"
)
sorted_pqt_files = sorted(folder.glob("*.parquet"))
pqt_file = [pqt.as_posix() for pqt in sorted_pqt_files]

# Access data via DuckDB
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

# Data pre-processing
df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

cols_to_numeric = ["open", "high", "low", "close"]
df[cols_to_numeric] = df[cols_to_numeric].apply(pd.to_numeric)


# =========================================================================
# REGIME DETECTION ENGINE
# =========================================================================


def calculate_regimes(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates Trend Direction & Strength to assign Market States."""
    # 1. Price trend direction indicators
    df["sma_50"] = df["close"].rolling(50).mean()
    df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()

    # 2. Volatility & Slope metrics
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            abs(df["high"] - df["close"].shift(1)),
            abs(df["low"] - df["close"].shift(1)),
        ),
    )
    df["atr"] = df["tr"].rolling(14).mean()

    # 10-period momentum/slope
    df["slope"] = (df["close"] - df["close"].shift(10)) / df["close"].shift(10)

    conditions = [
        (df["slope"] > 0.15),  # Strong Uptrend
        (df["slope"] > 0.03) & (df["slope"] <= 0.15),  # Weak Uptrend
        (df["slope"] < -0.15),  # Strong Downtrend
        (df["slope"] < -0.03) & (df["slope"] >= -0.15),  # Weak Downtrend
    ]
    choices = [
        "strong uptrend",
        "weak uptrend",
        "strong downtrend",
        "weak downtrend",
    ]

    # Assign state column; default to ranging
    df["state"] = np.select(conditions, choices, default="ranging")
    return df


def generate_regime_boxes(df: pd.DataFrame):
    """Groups continuous market states into 2D bounding boxes (x0, x1, y0, y1)."""
    # Create group IDs whenever state value changes
    df["state_group"] = (df["state"] != df["state"].shift(1)).cumsum()

    boxes = []
    for _, group in df.groupby("state_group"):
        state_label = group["state"].iloc[0]
        x0 = group["open_time"].iloc[0]
        x1 = group["open_time"].iloc[-1]

        # Fix zero-width box issue for 1-day state blocks
        if x0 == x1:
            x1 = x0 + pd.Timedelta(days=1)

        y0 = group["low"].min()
        y1 = group["high"].max()

        boxes.append(
            {
                "label": state_label,
                "x0": x0,
                "x1": x1,
                "y0": y0,
                "y1": y1,
            }
        )

    return boxes


# Color mapping for dim/subdued bounding box overlays
COLOR_MAP = {
    "strong uptrend": "rgba(38, 166, 154, 0.18)",
    "weak uptrend": "rgba(129, 199, 132, 0.12)",
    "strong downtrend": "rgba(239, 83, 80, 0.18)",
    "weak downtrend": "rgba(229, 115, 115, 0.12)",
    "ranging": "rgba(255, 213, 79, 0.10)",
}

# Execute calculation functions
df = calculate_regimes(df)
regime_boxes = generate_regime_boxes(df)

# =========================================================================
# PLOTLY CHARTING
# =========================================================================

fig = go.Figure()

# Add Candlestick Trace
fig.add_trace(
    go.Candlestick(
        x=df["open_time"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="OHLC",
        increasing_line_color="#26a69a",
        increasing_fillcolor="rgba(0, 0, 0, 0)",
        decreasing_line_color="#ef5350",
        decreasing_fillcolor="rgba(0, 0, 0, 0)",
    )
)

# Render 2D Market State Boxes & Annotations
for box in regime_boxes:
    # Add Rectangle Shape
    fig.add_shape(
        type="rect",
        x0=box["x0"],
        x1=box["x1"],
        y0=box["y0"],
        y1=box["y1"],
        fillcolor=COLOR_MAP.get(box["label"], "rgba(200, 200, 200, 0.1)"),
        line=dict(width=1, color="rgba(255, 255, 255, 0.15)"),
        layer="below",
    )
    # Add Floating Text Label above box
    fig.add_annotation(
        x=box["x0"],
        y=box["y1"],
        text=box["label"].upper(),
        showarrow=False,
        font=dict(size=9, color="#ffd54f"),
        yshift=8,
        xanchor="left",
    )

fig.update_layout(
    title="SOL Market Regime Identification",
    template="plotly_dark",
    xaxis_rangeslider_visible=False,
    hovermode="x unified",
    showlegend=False,
    height=700,
)

fig.show()