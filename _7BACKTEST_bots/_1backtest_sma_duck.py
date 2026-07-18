import pandas as pd
import numpy as np
import duckdb
import json
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# BACKTEST ENGINE REWRITTEN WITH duckdb and plotly _ AND parquet files
# ==============================================================================
# 1. CONFIGURATION & FILE PATHS
# ==============================================================================
stt = datetime.now() # startime

# Setup paths based on the current file's location
cwd = Path(__file__).resolve()
this_folder = cwd.parent.parent

# Input Data
# DATA_FILE = data_folder / 'SOLUSDT-1m-2026-06-02.csv'
DATA_FILE = this_folder / '_1inputs' / 'WLDUSDT-1m-2024-12.csv'

# Output Files
#---------------ensure out put folder exists
out_folder = this_folder/'_5outputs'
out_folder.mkdir(parents=True, exist_ok=True)

# symbol name
SYMBOL = DATA_FILE.name.split("-")[0] # ie WLDUSDT
timenow= datetime.now().strftime("%d_%H%M%S")

JOURNAL_FILE = out_folder/ f"{SYMBOL}_journal-{timenow}.csv"
STATS_FILE = out_folder/f"{SYMBOL}_stats-{timenow}.json" 
EQUITY_CHART = out_folder/f"{SYMBOL}_equitycurve-{timenow}.png"

# Strategy & Account Parameters
STARTING_CAPITAL = 100000.0
POSITION_SIZE_USD = 5000.0
# Assuming 0.1% fee per transaction (standard crypto taker fee)
FEE_RATE = 0.001
STOP_LOSS_PCT = 0.10        # 10% Stop Loss
TAKE_PROFIT_PCT = 0.50      # 50% Take Profit
SMA_LONG = 200
SMA_SHORT = 65
HMA_PERIOD = 65

# ==============================================================================
# 2. INDICATOR FUNCTIONS
# ==============================================================================


def calculate_wma(series, period):
    """Calculates the Weighted Moving Average (WMA)."""
    weights = np.arange(1, period + 1)
    # Using rolling apply with numpy dot product for the weighted average
    return series.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)


def calculate_hma(series, period):
    """Calculates the Hull Moving Average (HMA)."""
    half_length = int(period / 2)
    sqrt_length = int(np.sqrt(period))

    wma_half = calculate_wma(series, half_length)
    wma_full = calculate_wma(series, period)

    # HMA Formula: WMA(2 * WMA(n/2) - WMA(n)), sqrt(n))
    diff = 2 * wma_half - wma_full
    return calculate_wma(diff, sqrt_length)

# ==============================================================================
# 3. BACKTESTING ENGINE
# ==============================================================================

def main():
    print("Loading historical data...")
    try:
        # Read the Binance  data
        conn = duckdb.connect(":memory:")
        qry = f"""--sql
            select 
            open_time,
            open,
            high,
            low,
            close,
            volume,
            close_time,
            quote_volume
            from read_csv('{DATA_FILE}')
            """

        df= conn.sql(qry).df()
        conn.close()
    except FileNotFoundError:
        print(f"Error: Data file not found at {DATA_FILE}")
        return

    # Convert Binance open_time (usually milliseconds) to readable datetime
    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')

    print("Calculating indicators (SMA and HMA)...")
    df['SMA_200'] = df['close'].rolling(window=SMA_LONG).mean()
    df['SMA_65'] = df['close'].rolling(window=SMA_SHORT).mean()
    df['HMA_65'] = calculate_hma(df['close'], period=HMA_PERIOD)

    # Drop rows where indicators are not yet calculated to avoid errors at the start
    df.dropna(subset=['SMA_200', 'HMA_65'], inplace=True)
    df.reset_index(drop=True, inplace=True)

    print("Starting backtest execution...")

    # State tracking variables
    equity_balance = STARTING_CAPITAL
    in_position = False
    current_side = None
    entry_price = 0.0
    entry_time = None
    qty = 0.0
    entry_fee = 0.0

    # Statistics tracking
    trade_journal = []
    trade_number = 1
    sl_hits = 0
    tp_hits = 0
    peak_equity = STARTING_CAPITAL
    max_drawdown = 0.0

    # Iterate through the dataframe row by row to simulate live market conditions
    for i in range(1, len(df)):
        current_row = df.iloc[i]
        prev_row = df.iloc[i-1]

        current_price = current_row['close']
        current_high = current_row['high']
        current_low = current_row['low']
        current_time = current_row['datetime']

        # Indicator states
        uptrend = current_price > current_row['SMA_200']
        downtrend = current_price < current_row['SMA_200']

        # Crossovers
        hma_crossed_above = (prev_row['HMA_65'] <= prev_row['SMA_65']) and (
            current_row['HMA_65'] > current_row['SMA_65'])
        hma_crossed_below = (prev_row['HMA_65'] >= prev_row['SMA_65']) and (
            current_row['HMA_65'] < current_row['SMA_65'])

        # --- 3A. MANAGE OPEN POSITIONS ---
        if in_position:
            exit_reason = None
            exit_price = 0.0

            # Check Stop Loss & Take Profit (Intra-candle highs/lows)
            if current_side == "Long":
                sl_price = entry_price * (1 - STOP_LOSS_PCT)
                tp_price = entry_price * (1 + TAKE_PROFIT_PCT)

                if current_low <= sl_price:
                    exit_reason, exit_price = "SL", sl_price
                    sl_hits += 1
                elif current_high >= tp_price:
                    exit_reason, exit_price = "TP", tp_price
                    tp_hits += 1
                elif hma_crossed_below:
                    exit_reason, exit_price = "Signal", current_price

            elif current_side == "Short":
                sl_price = entry_price * (1 + STOP_LOSS_PCT)
                tp_price = entry_price * (1 - TAKE_PROFIT_PCT)

                if current_high >= sl_price:
                    exit_reason, exit_price = "SL", sl_price
                    sl_hits += 1
                elif current_low <= tp_price:
                    exit_reason, exit_price = "TP", tp_price
                    tp_hits += 1
                elif hma_crossed_above:
                    exit_reason, exit_price = "Signal", current_price

            # Execute the Exit
            if exit_reason:
                exit_fee = (qty * exit_price) * FEE_RATE

                if current_side == "Long":
                    gross_pnl = (exit_price - entry_price) * qty
                else:
                    gross_pnl = (entry_price - exit_price) * qty

                net_pnl = gross_pnl - entry_fee - exit_fee
                equity_balance += net_pnl

                # Track Max Drawdown
                if equity_balance > peak_equity:
                    peak_equity = equity_balance
                current_drawdown = (peak_equity - equity_balance) / peak_equity
                if current_drawdown > max_drawdown:
                    max_drawdown = current_drawdown

                # Log Trade
                trade_journal.append({
                    "Trade number": trade_number,
                    "Symbol": SYMBOL,
                    "Side": current_side,
                    "Entry Time": entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "Entry Price": entry_price,
                    "Exit Time": current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "Exit Price": exit_price,
                    "Qty": qty,
                    "Entry Fee": entry_fee,
                    "Exit Fee": exit_fee,
                    "Gross PnL": gross_pnl,
                    "Net PnL": net_pnl,
                    "Equity_balance": equity_balance,
                    "Exit Reason": exit_reason
                })

                trade_number += 1
                in_position = False
                current_side = None

        # --- 3B. LOOK FOR NEW ENTRIES ---
        if not in_position:
            if uptrend and hma_crossed_above:
                current_side = "Long"
            elif downtrend and hma_crossed_below:
                current_side = "Short"

            if current_side:
                in_position = True
                entry_price = current_price
                entry_time = current_time
                qty = POSITION_SIZE_USD / entry_price
                entry_fee = (qty * entry_price) * FEE_RATE

    # ==============================================================================
    # 4. DATA OUTPUT & REPORTING
    # ==============================================================================

    print("Backtest complete. Generating reports...")

     # 4A. Save Trade Journal (.csv)
    journal_df = pd.DataFrame(trade_journal)
    # Reorder columns as requested (omitting internal 'Exit Reason' from final output if desired, but keeping it is helpful)
    columns_order = [
        "Trade number", "Symbol", "Side", "Entry Time", "Entry Price",
        "Exit Time", "Exit Price", "Qty", "Entry Fee", "Exit Fee",
        "Gross PnL", "Net PnL", "Equity_balance"
    ]
    if not journal_df.empty:
        journal_df[columns_order].to_csv(JOURNAL_FILE, index=False)
    else:
        print("No trades were executed during this period.")
        return
    # print(journal_df.tail())
    #--------------------------------------

    # 4B. Calculate Statistics
    total_trades = len(journal_df)
    winning_trades = len(journal_df[journal_df['Net PnL'] > 0])
    losing_trades = len(journal_df[journal_df['Net PnL'] <= 0])
    win_rate = winning_trades / total_trades if total_trades > 0 else 0

    gross_profit = journal_df[journal_df['Gross PnL'] > 0]['Gross PnL'].sum()
    gross_loss = journal_df[journal_df['Gross PnL'] < 0]['Gross PnL'].sum()
    net_profit = journal_df['Net PnL'].sum()

    profit_factor = abs(
        gross_profit / gross_loss) if gross_loss != 0 else float('inf')
    average_win = journal_df[journal_df['Net PnL'] >
                             0]['Net PnL'].mean() if winning_trades > 0 else 0
    average_loss = journal_df[journal_df['Net PnL'] <=
                              0]['Net PnL'].mean() if losing_trades > 0 else 0

    # Expectancy = (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
    expectancy = (win_rate * average_win) - \
        ((1 - win_rate) * abs(average_loss))

    total_fees = journal_df['Entry Fee'].sum() + journal_df['Exit Fee'].sum()

    stats = {
        "Total Trades": total_trades,
        "Winning Trades": winning_trades,
        "Losing Trades": losing_trades,
        "Win Rate": f"{win_rate * 100:.2f}%",
        "Gross Profit": round(gross_profit, 2),
        "Gross Loss": round(gross_loss, 2),
        "Net Profit": round(net_profit, 2),
        "Profit Factor": round(profit_factor, 2),
        "Average Win": round(average_win, 2),
        "Average Loss": round(average_loss, 2),
        "Expectancy": round(expectancy, 2),
        "Maximum Drawdown": f"{max_drawdown * 100:.2f}%",
        "Total Fees Paid": round(total_fees, 2),
        "Stop_losses_hit": sl_hits,
        "Target_profits_hit": tp_hits
    }

    # Save Stats (.json)
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=4)
    # print stats

    for key, value in stats.items():
        print(f"{key}: {value}")
    #------------------------------------

    # 4C. Plot Equity Curve (.png)
    
    # Include starting capital as trade 0 for a complete chart
    trades = [0] + journal_df['Trade number'].tolist()
    equity = [STARTING_CAPITAL] + journal_df['Equity_balance'].tolist()

    # plt.figure(figsize=(12, 6))
    # plt.plot(trades, equity, label='Equity Balance', color='blue', linewidth=2)
    # plt.title('Strategy Equity Curve', fontsize=16)
    # plt.xlabel('Trade Number', fontsize=12)
    # plt.ylabel('Equity Balance (USD)', fontsize=12)
    # plt.axhline(y=STARTING_CAPITAL, color='red',
    #             linestyle='--', label='Starting Capital')
    # plt.grid(True, alpha=0.3)
    # plt.legend()
    # plt.tight_layout()
    # plt.savefig(EQUITY_CHART)
    # plt.close()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=trades, y=equity, mode= 'lines'))
    chart= fig.show()

    # print(chart)


    run_duration = datetime.now() - stt
    print(f"\nrun time : {run_duration}")
    
if __name__ == "__main__":
    main()