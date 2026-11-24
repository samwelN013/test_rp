from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
HIST_DIR = BASE_DIR / "binance_aggts_hist"

# Exact uncommented column list from your notebook
FWD_COLS = [
    "open_time",
    "potential_pivot_bh",
    "actual_pivot_bh",
    "swing_point_wcks_bh",
    "price_bull_dominance",
    "price_bear_dominance",
    "price_bull_persistence",
    "price_bear_persistence",
    "rvol_persistence",
    "rvol_intensity",
    "bar_volatility_bh",
    "rvol_bh",
    "delta_imbalance_pct_bh",
    "delta_divergence",
    "prc_change_window_bh",
    "rel_price_pct_change",
    "return_to_pivot_pct",
    "std_delta_bull_dominance",
    "std_delta_bear_dominance",
    "buy_ratio_bh",
    "buy_pressure_persistence",
    "sell_ratio_bh",
    "sell_pressure_persistence",
    "bars_to_pivot",
]


def get_available_symbols() -> list[str]:
    """Scans binance_aggts_hist/ for *_current_data folders and returns sorted symbol names."""
    if not HIST_DIR.exists():
        return []
    symbols = []
    for item in sorted(HIST_DIR.iterdir()):
        if item.is_dir() and item.name.endswith("_current_data"):
            symbol = item.name.replace("_current_data", "")
            symbols.append(symbol)
    return symbols


def _load_aggregated_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame:
    """Queries Parquet files via DuckDB using your exact daily vs hourly file split."""
    folder = HIST_DIR / f"{symbol.upper()}_current_data"
    if not folder.exists():
        raise FileNotFoundError(f"Symbol folder not found: {folder}")

    all_files = sorted(folder.glob("*.parquet"))
    daily_files = [f.as_posix() for f in all_files if "_H" not in f.name]
    hourly_shards = [f.as_posix() for f in all_files if "_H" in f.name]

    if timeframe == "1 Day":
        target_files = daily_files
    elif timeframe == "1 Hour":
        target_files = daily_files[-2:] + hourly_shards
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    if not target_files:
        return pd.DataFrame()

    conn = duckdb.connect(database=":memory:")
    try:
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
        FROM read_parquet({target_files})
        GROUP BY 1
        ORDER BY open_time ASC;
        """
        df = conn.execute(qry).df()
    finally:
        conn.close()

    return df


def _compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Runs your exact market microstructure, pivot, and directional behavior calculations."""
    if df.empty:
        return df

    # PART 1: RAW MARKET MEGA METRICS
    df["totalVol_usdt"] = (df["buyVol_usdt"] + df["sellVol_usdt"]).round(3)
    df["volume_ma20"] = df["totalVol_usdt"].rolling(window=20).mean()
    df["delta"] = (df["buyVol_usdt"] - df["sellVol_usdt"]).round(3)

    df["prc_change_window"] = ((df["close"] - df["open"]) / df["open"]) * 100

    is_bull = df["close"] >= df["open"]
    df["full_pct_change"] = np.where(
        is_bull,
        ((df["high"] - df["low"]) / df["low"]) * 100,
        ((df["low"] - df["high"]) / df["high"]) * 100,
    )

    absolute_pct_change = df["prc_change_window"].abs()
    df["prc_change_ma20"] = absolute_pct_change.rolling(20).mean()
    df["rel_prc_change"] = absolute_pct_change / df["prc_change_ma20"]
    df["bar_volatility"] = ((df["high"] - df["low"]) / df["open"]) * 100
    df["s_delta_pct"] = (df["delta"] / df["volume_ma20"]) * 100

    delta_abs_mean = df["delta"].abs().rolling(20).mean()
    delta_std_abs = df["delta"].abs().rolling(20).std()
    df["standzd_delta"] = df["delta"] / delta_abs_mean
    df["standzd_delta_dev_zscore"] = ((df["delta"] - delta_abs_mean) / delta_std_abs).abs()

    # PART 2: PIVOT POINTS OF CANDLE WICKS & BODIES
    left_len = 10
    right_len = 10
    window_size = left_len + right_len + 1

    rolling_max = df["high"].rolling(window=window_size, center=True).max()
    rolling_min = df["low"].rolling(window=window_size, center=True).min()

    df["pivot_high"] = df["high"].where(df["high"] == rolling_max, None)
    df["pivot_low"] = df["low"].where(df["low"] == rolling_min, None)
    df["swing_point_wcks"] = df["pivot_high"].combine_first(df["pivot_low"])

    df["pivot_h_raw"] = df["high"].where(df["high"] == rolling_max, None)
    df["pivot_l_raw"] = df["low"].where(df["low"] == rolling_min, None)

    body_top = df[["open", "close"]].max(axis=1)
    body_bottom = df[["open", "close"]].min(axis=1)

    df["pivot_high_bdy"] = np.where(df["pivot_h_raw"].notna(), body_top, None)
    df["pivot_low_bdy"] = np.where(df["pivot_l_raw"].notna(), body_bottom, None)
    df["swing_point_bdy"] = df["pivot_high_bdy"].combine_first(df["pivot_low_bdy"])
    df = df.drop(columns=["pivot_h_raw", "pivot_l_raw"])

    # PART 3: INTERNAL METRICS OF SWING MOVES
    df["swing_group_wck"] = df["swing_point_wcks"].notna().cumsum().shift(1, fill_value=0)
    df["cum_buyVol_internal"] = df.groupby("swing_group_wck")["buyVol_usdt"].cumsum()
    df["cum_sellVol_internal"] = df.groupby("swing_group_wck")["sellVol_usdt"].cumsum()
    df["cum_totalVol_internal"] = df.groupby("swing_group_wck")["totalVol_usdt"].cumsum()
    df["cum_delta_internal"] = df.groupby("swing_group_wck")["delta"].cumsum()

    df["is_pivot"] = df["swing_point_bdy"].notna()
    df["swing_group_bdy"] = df["is_pivot"].cumsum()
    df["pivot_anchor"] = df.groupby("swing_group_bdy")["swing_point_bdy"].transform("first")

    first_candle_open = float(df["open"].iloc[0])
    first_candle_close = float(df["close"].iloc[0])
    body_top_first = max([first_candle_open, first_candle_close])
    body_bottom_first = min([first_candle_open, first_candle_close])
    valid_anchors = df["pivot_anchor"].dropna()

    if len(valid_anchors) > 0:
        first_valid_pivot = valid_anchors.iloc[0]
        pre_swing_start_price = (
            body_bottom_first if first_valid_pivot > first_candle_open else body_top_first
        )
    else:
        pre_swing_start_price = first_candle_open

    df["swing_start_price"] = df["pivot_anchor"].fillna(pre_swing_start_price)
    df["pct_change_from_pivot"] = (
        (df["close"] - df["swing_start_price"]) / df["swing_start_price"]
    ) * 100
    df = df.drop(columns=["is_pivot", "pivot_anchor"])

    df["cum_delta_all"] = df["delta"].cumsum()
    df = df.drop(columns=["swing_group_wck", "swing_group_bdy", "swing_start_price"])

    # PART 4: POTENTIAL PIVOT, ACTUAL PIVOT, RVOL, ATR, STOPS
    prev_left_max = df["high"].shift(1).rolling(window=left_len).max()
    prev_left_min = df["low"].shift(1).rolling(window=left_len).min()

    is_potential_short = df["high"] > prev_left_max
    is_potential_long = df["low"] < prev_left_min
    df["potential_pivot"] = np.select(
        [is_potential_short, is_potential_long], ["S", "L"], default=None
    )

    df["actual_pivot_h"] = np.where(df["pivot_high"].notna(), "S", None)
    df["actual_pivot_l"] = np.where(df["pivot_low"].notna(), "L", None)
    df["actual_pivot"] = df["actual_pivot_h"].combine_first(df["actual_pivot_l"])
    df = df.drop(columns=["actual_pivot_h", "actual_pivot_l"])

    df["rvol"] = df["totalVol_usdt"] / df["volume_ma20"]

    atr_period = 14
    prev_close = df["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()
    df["TR"] = np.maximum(tr1, np.maximum(tr2, tr3))
    df["ATR"] = df["TR"].rolling(window=atr_period).mean()
    df = df.drop(columns=["TR"])

    atr_multiplier = 1.50
    df["longstop"] = df["open"] - (df["ATR"] * atr_multiplier)
    df["shortstop"] = df["open"] + (df["ATR"] * atr_multiplier)

    # CURRENT MARKET STATE (bf)
    bf = df[df["rvol"].notna()].reset_index(drop=True)
    if bf.empty:
        return bf

    bf = bf.sort_values("open_time").reset_index(drop=True)
    close_bh = bf["close"]
    w_sz = 3

    bf["price_return_3"] = close_bh.pct_change(w_sz) * 100
    bf["price_velocity"] = bf["price_return_3"] / w_sz
    bf["rel_price_pct_change"] = bf["rel_prc_change"]
    bf["bar_volatility_bh"] = bf["bar_volatility"]
    bf["potential_pivot_bh"] = bf["potential_pivot"]
    bf["actual_pivot_bh"] = bf["actual_pivot"]
    bf["swing_point_wcks_bh"] = bf["swing_point_wcks"]
    bf["close_bh"] = bf["close"]
    bf["prc_change_window_bh"] = bf["prc_change_window"]

    # Directional Price Features
    x_prc = bf["prc_change_window_bh"]
    bull_p = x_prc.clip(lower=0)
    bear_p = (-x_prc).clip(lower=0)
    bull_count = x_prc.gt(0).rolling(3, min_periods=3).sum()
    bear_count = x_prc.lt(0).rolling(3, min_periods=3).sum()

    bf["price_bull_persistence"] = (bull_count / 3) * 100
    bf["price_bear_persistence"] = (bear_count / 3) * 100
    bf["price_bull_intensity"] = bull_p.rolling(3, min_periods=3).sum() / bull_count.replace(0, np.nan)
    bf["price_bear_intensity"] = bear_p.rolling(3, min_periods=3).sum() / bear_count.replace(0, np.nan)
    bf["price_bull_activity"] = bull_p.rolling(3, min_periods=3).mean()
    bf["price_bear_activity"] = bear_p.rolling(3, min_periods=3).mean()

    denom_prc = bf["price_bear_activity"] + bf["price_bull_activity"]
    bf["price_bull_dominance"] = (bf["price_bull_activity"] / denom_prc) * 100
    bf["price_bear_dominance"] = (bf["price_bear_activity"] / denom_prc) * 100

    # Volume Behavior
    bf["delta_bh"] = bf["delta"]
    bf["totalVol_bh"] = bf["totalVol_usdt"]
    bf["rvol_bh"] = bf["rvol"]
    bf["rvol_persistence"] = bf["rvol_bh"].ge(1.0).rolling(3, min_periods=3).mean() * 100
    bf["rvol_intensity"] = bf["rvol_bh"].rolling(3, min_periods=3).mean()

    # Delta Behavior
    bf["s_delta_pct_bh"] = bf["s_delta_pct"]
    bf["delta_imbalance_pct_bh"] = (bf["delta_bh"] / bf["totalVol_bh"]) * 100
    bf["standzd_delta_bh"] = bf["standzd_delta"]
    bf["standzd_delta_dev_bh"] = bf["standzd_delta_dev_zscore"]

    x_dlt = bf["standzd_delta_bh"]
    bull_d = x_dlt.clip(lower=0)
    bear_d = (-x_dlt).clip(lower=0)
    bf["std_delta_bull_activity"] = bull_d.rolling(3, min_periods=3).mean()
    bf["std_delta_bear_activity"] = bear_d.rolling(3, min_periods=3).mean()

    denom_dlt = bf["std_delta_bear_activity"] + bf["std_delta_bull_activity"]
    bf["std_delta_bull_dominance"] = (bf["std_delta_bull_activity"] / denom_dlt) * 100
    bf["std_delta_bear_dominance"] = (bf["std_delta_bear_activity"] / denom_dlt) * 100
    bf["delta_divergence"] = (bf["standzd_delta_bh"] * bf["prc_change_window_bh"]) < 0

    # Buy/Sell Ratio Behavior
    bf["buy_ratio_bh"] = (bf["buyVol_usdt"] / bf["totalVol_bh"]) * 100
    bf["buy_pressure_persistence"] = bf["buy_ratio_bh"].rolling(3, min_periods=3).mean()
    bf["sell_ratio_bh"] = (bf["sellVol_usdt"] / bf["totalVol_bh"]) * 100
    bf["sell_pressure_persistence"] = bf["sell_ratio_bh"].rolling(3, min_periods=3).mean()

    # Candle Anatomy
    bf["open_bh"] = bf["open"]
    bf["low_bh"] = bf["low"]
    bf["high_bh"] = bf["high"]
    candle_range = bf["high_bh"] - bf["low_bh"]
    bf["upper_wick_pct"] = ((bf["high_bh"] - bf[["open_bh", "close_bh"]].max(axis=1)) / candle_range) * 100
    bf["body_pct"] = ((bf["close_bh"] - bf["open_bh"]).abs() / candle_range) * 100
    bf["lower_wick_pct"] = ((bf[["open_bh", "close_bh"]].min(axis=1) - bf["low_bh"]) / candle_range) * 100
    bf.loc[candle_range == 0, ["upper_wick_pct", "body_pct", "lower_wick_pct"]] = np.nan

    # Outcome Analysis (To the Pivot)
    pivot_mask = bf["swing_point_wcks"].notna()
    pivot_positions = np.flatnonzero(pivot_mask.to_numpy())

    bf["return_to_pivot_pct"] = np.nan
    bf["return_price_velocity"] = np.nan
    bf["bars_to_pivot"] = np.nan

    opens = bf["open"].to_numpy(dtype=float)
    closes = bf["close"].to_numpy(dtype=float)
    pivot_close_prices = closes[pivot_positions]

    for i in range(len(bf)):
        next_idx = np.searchsorted(pivot_positions, i, side="right")
        if next_idx >= len(pivot_positions):
            continue
        pivot_pos = pivot_positions[next_idx]
        start_price = opens[i]
        end_price = pivot_close_prices[next_idx]
        bars = pivot_pos - i
        if not np.isfinite(start_price) or start_price <= 0:
            continue

        return_pct = ((end_price - start_price) / start_price) * 100
        velocity = return_pct / bars if bars > 0 else np.nan

        bf.iloc[i, bf.columns.get_loc("return_to_pivot_pct")] = return_pct
        bf.iloc[i, bf.columns.get_loc("return_price_velocity")] = velocity
        bf.iloc[i, bf.columns.get_loc("bars_to_pivot")] = bars

    return bf


def style_trading_df(
    df: pd.DataFrame,
    cols: list[str] | None = None,
    max_height: str = "525px",  # Caps visible viewport to 21 rows (1 header + 20 data rows)
    table_uuid: str = "wynan_tbl",
) -> str:
    """Renders your exact Jupyter HTML/CSS styled DataFrame with sticky header & open_time column."""
    if df.empty:
        return "<div style='padding:16px;color:#9aa0a6;'>No rows available yet (needs at least 20 bars for rolling metrics).</div>"

    sub_df = df.copy()
    if cols is not None:
        sub_df = sub_df[[c for c in cols if c in sub_df.columns]]

    if "open_time" in sub_df.columns:
        sub_df = sub_df.set_index("open_time")
        sub_df.index.name = None

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

    pos_neg_cols = [
        "prc_change_window_bh",
        "price_return_3",
        "price_velocity",
        "standzd_delta_bh",
        "delta_imbalance_pct_bh",
        "return_to_pivot_pct",
        "return_price_velocity",
    ]

    threshold_cols = {
        "buy_ratio_bh": (50.0, "#2ecc71", "#e74c3c"),
        "sell_ratio_bh": (50.0, "#cb7de3", "#3d8eeb"),
    }

    bool_cols = {
        "delta_divergence": ("#c7d830", "#1c85e7"),
    }

    bg_highlight_cols = ["return_to_pivot_pct", "return_price_velocity", "bars_to_pivot"]

    def color_boolean(val, true_color, false_color):
        if pd.isna(val):
            return ""
        s = str(val).strip().lower()
        if s in ["true", "1", "1.0"]:
            return f"color: {true_color}; font-weight: normal;"
        if s in ["false", "0", "0.0"]:
            return f"color: {false_color}; font-weight: normal;"
        return ""

    def highlight_signal_rows(row):
        styles = [""] * len(row)
        swing = row.get("swing_point_wcks_bh", np.nan)
        pot_piv = str(row.get("potential_pivot_bh", ""))
        act_piv = str(row.get("actual_pivot_bh", ""))

        bg_color = None
        if pd.isna(swing) or swing == "":
            if pot_piv == "S":
                bg_color = "background-color: #222847; color: white;"
            elif pot_piv == "L":
                bg_color = "background-color: #3d3a12; color: white;"
        else:
            if act_piv == "S":
                bg_color = "background-color: #6a396b; color: white;"
            elif act_piv == "L":
                bg_color = "background-color: #396145; color: white;"

        if bg_color:
            return [bg_color] * len(row)
        return styles

    def color_pos_neg(val):
        if pd.isna(val):
            return ""
        if val > 0:
            return "color: #2ecc71; font-weight: normal;"
        if val < 0:
            return "color: #e74c3c; font-weight: normal;"
        return ""

    def color_threshold(val, thresh, high_color, low_color):
        if pd.isna(val):
            return ""
        if val > thresh:
            return f"color: {high_color}; font-weight: normal;"
        if val < thresh:
            return f"color: {low_color}; font-weight: normal;"
        return ""

    styler = sub_df.style
    styler = styler.apply(highlight_signal_rows, axis=1)

    for col, color in static_color_cols.items():
        if col in sub_df.columns:
            styler = styler.map(lambda v, c=color: f"color: {c}; font-weight: normal;", subset=[col])

    valid_pos_neg = [c for c in pos_neg_cols if c in sub_df.columns]
    if valid_pos_neg:
        styler = styler.map(color_pos_neg, subset=valid_pos_neg)

    for col, (thresh, high_c, low_c) in threshold_cols.items():
        if col in sub_df.columns:
            styler = styler.map(
                lambda v, t=thresh, h=high_c, l=low_c: color_threshold(v, t, h, l),
                subset=[col],
            )

    for col, (true_c, false_c) in bool_cols.items():
        if col in sub_df.columns:
            styler = styler.map(
                lambda v, tc=true_c, fc=false_c: color_boolean(v, tc, fc),
                subset=[col],
            )

    valid_bg_cols = [c for c in bg_highlight_cols if c in sub_df.columns]
    if valid_bg_cols:
        styler = styler.map(lambda v: "background-color: #2e1342;", subset=valid_bg_cols)

    default_format = {
        "swing_point_wcks_bh": "{:.2f}",
        "upper_wick_pct": "{:.0f} %",
        "body_pct": "{:.0f} %",
        "lower_wick_pct": "{:.0f} %",
        "close_bh": "{:.2f}",
        "bar_volatility_bh": "{:.2f} %",
        "prc_change_window_bh": "{:+.2f} %",
        "price_bull_persistence": "{:.0f} %",
        "price_bull_intensity": "{:.3f}",
        "price_bear_persistence": "{:.0f} %",
        "price_bear_intensity": "{:.3f}",
        "price_bull_activity": "{:.3f}",
        "price_bear_activity": "{:.3f}",
        "price_bull_dominance": "{:.0f} %",
        "price_bear_dominance": "{:.0f} %",
        "rel_price_pct_change": "{:.2f}",
        "price_return_3": "{:.2f} %",
        "price_velocity": "{:+.2f} %",
        "rvol_bh": "{:.2f}",
        "rvol_persistence": "{:.0f} %",
        "rvol_intensity": "{:.2f}",
        "standzd_delta_bh": "{:.2f}",
        "std_delta_bull_dominance": "{:.0f} %",
        "std_delta_bear_dominance": "{:.0f} %",
        "std_delta_bull_activity": "{:.2f}",
        "std_delta_bear_activity": "{:.2f}",
        "delta_imbalance_pct_bh": "{:.2f} %",
        "buy_ratio_bh": "{:.2f}",
        "buy_pressure_persistence": "{:.2f}",
        "sell_ratio_bh": "{:.2f}",
        "sell_pressure_persistence": "{:.2f}",
        "return_to_pivot_pct": "{:.2f} %",
        "return_price_velocity": "{:.2f} %",
        "bars_to_pivot": "{:.0f}",
    }

    active_format = {k: v for k, v in default_format.items() if k in sub_df.columns}
    styler = styler.format(active_format, na_rep="-")

    table_css = [
        {
            "selector": "",
            "props": [
                ("max-height", max_height),
                ("overflow", "auto"),
                ("display", "block"),
                ("border-collapse", "separate"),
                ("border-spacing", "0"),
                ("font-family", "'JetBrains Mono', 'Fira Code', Consolas, monospace"),
                ("font-size", "12px"),
            ],
        },
        {
            "selector": "td",
            "props": [
                ("height", "16px"),
                ("min-height", "16px"),
                ("max-height", "16px"),
                ("padding", "4px 8px"),
                ("white-space", "nowrap"),
                ("text-align", "center !important"),
                ("border-bottom", "1px solid #2b2b2b"),
                ("border-right", "1px solid #262626"),
            ],
        },
        {
            "selector": "th",
            "props": [
                ("padding", "6px 8px"),
                ("white-space", "nowrap"),
                ("text-align", "center !important"),
                ("border-bottom", "1px solid #3a3a3a"),
                ("border-right", "1px solid #333333"),
            ],
        },
        {
            "selector": "th.col_heading",
            "props": [
                ("background-color", "#423a42 !important"),
                ("color", "#ffffffbe !important"),
                ("position", "sticky !important"),
                ("top", "0 !important"),
                ("z-index", "3 !important"),
            ],
        },
        {
            "selector": "th.row_heading",
            "props": [
                ("background-color", "#1e1e1e !important"),
                ("color", "#d6df58d6 !important"),
                ("position", "sticky !important"),
                ("left", "0 !important"),
                ("z-index", "2 !important"),
            ],
        },
        {
            "selector": "th.blank",
            "props": [
                ("background-color", "#423a42 !important"),
                ("position", "sticky !important"),
                ("top", "0 !important"),
                ("left", "0 !important"),
                ("z-index", "4 !important"),
            ],
        },
    ]

    styler = (
        styler.set_sticky(axis=0)
        .set_sticky(axis=1)
        .set_table_styles(table_css)
    )

    return styler.to_html(table_uuid=table_uuid)


def build_symbol_tables(symbol: str) -> dict:
    """Builds both the 1-Day and 1-Hour styled HTML tables for a given symbol."""
    symbol = symbol.upper()

    df_1d = _load_aggregated_ohlcv(symbol, "1 Day")
    bf_1d = _compute_features(df_1d)
    html_1d = style_trading_df(bf_1d, cols=FWD_COLS, max_height="525px", table_uuid=f"{symbol}_1d")

    df_1h = _load_aggregated_ohlcv(symbol, "1 Hour")
    bf_1h = _compute_features(df_1h)
    html_1h = style_trading_df(bf_1h, cols=FWD_COLS, max_height="525px", table_uuid=f"{symbol}_1h")

    return {
        "symbol": symbol,
        "rows_1d": int(len(bf_1d)),
        "rows_1h": int(len(bf_1h)),
        "html_1d": html_1d,
        "html_1h": html_1h,
    }