from datetime import datetime
import pandas as pd
from pybit.unified_trading import HTTP
from pathlib import Path
# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
journal_folder = Path(__file__).resolve().parent/'_output_j'
journal_path = journal_folder/'main_crypto_journal.csv'
#  API credentials:
API_KEY = "KtKADX3GIyPFbRItgj"
API_SECRET = "dvX94tGVd7wldCIXdjsPo6XEliNhGXaVluir"
# Set testnet=False, demo = True since am using live account's demo section
TESTNET = False
DEMO = True
# Initialize HTTP Session
session = HTTP(
    testnet=TESTNET,
    demo=DEMO,
    api_key=API_KEY,
    api_secret=API_SECRET,
)


def get_wallet_balance() -> float:
    """Fetch current total equity/account balance in USDT."""
    try:
        response = session.get_wallet_balance(
            accountType="UNIFIED", coin="USDT")
        result = response.get("result", {}).get("list", [])
        if result:
            return float(result[0].get("totalEquity", 0.0))
    except Exception as e:
        print(f"Error fetching account balance: {e}")
    return 0.0


def fetch_closed_trades():
    """Fetch closed USDT Perpetual trade history and format into 17 columns."""
    current_balance = get_wallet_balance()

    # Fetch closed PnL records for Linear (USDT/USDC Perpetual) instruments
    response = session.get_closed_pnl(category="linear", limit=50)
    records = response.get("result", {}).get("list", [])

    journal_rows = []

    for index, trade in enumerate(reversed(records), start=1):
        symbol = trade.get("symbol", "")

        # Filter strictly for USDT Perpetual pairs (e.g., BTCUSDT)
        if not symbol.endswith("USDT"):
            continue

        # Extract PnL & Order Details
        side = trade.get("side", "")  # Buy/Sell
        qty = float(trade.get("qty", 0.0))
        entry_price = float(trade.get("avgEntryPrice", 0.0))
        exit_price = float(trade.get("avgExitPrice", 0.0))
        pnl = float(trade.get("closedPnl", 0.0))

        filled_value = qty * entry_price

        # Dates & Time handling (Bybit returns timestamps in milliseconds)
        created_time_ms = int(trade.get("createdTime", 0))
        updated_time_ms = int(trade.get("updatedTime", 0))

        entry_date = (
            datetime.fromtimestamp(created_time_ms / 1000)
            if created_time_ms
            else None
        )
        exit_date = (
            datetime.fromtimestamp(updated_time_ms / 1000)
            if updated_time_ms
            else None
        )

        days_in_trade = (
            round((updated_time_ms - created_time_ms) / (1000 * 60 * 60 * 24), 2)
            if (created_time_ms and updated_time_ms)
            else 0.0
        )

        # Map Side to Long / Short
        trade_side = "Long" if side.lower() == "buy" else "Short"

        # Construct row matching your 17 exact columns
        row = {
            "trade number": index,
            "symbol": symbol,
            "side": trade_side,
            "filled qty": qty,
            "filled value (usdt)": round(filled_value, 4),
            # Estimated taker/maker fee
            "fill fee": float(trade.get("cumEntryValue", 0.0)) * 0.0006,
            "exit fee": float(trade.get("cumExitValue", 0.0)) * 0.0006,
            "avg fill price": entry_price,
            "exit price": exit_price,
            "PnL": round(pnl, 4),
            "account balance": current_balance,
            "entry date": entry_date.strftime("%Y-%m-%d %H:%M:%S") if entry_date else "N/A",
            "exit date": exit_date.strftime("%Y-%m-%d %H:%M:%S") if exit_date else "N/A",
            "days in a trade": days_in_trade,
            "order type entry": trade.get("execType", "Market/Limit"),
            "order type exit": "Market/Limit",
            "instrument": "USDT Perpetuals",
        }
        journal_rows.append(row)

    return journal_rows


def export_to_csv(rows, filename=journal_path):
    if not rows:
        print("No trades found to write.")
        return

    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False)
    print(f"Successfully exported {len(rows)} trades to '{filename.name}'!")


if __name__ == "__main__":
    trades = fetch_closed_trades()
    export_to_csv(trades)
    # print(journal_path.exists())
    # "bybit_trading_journal.csv"
