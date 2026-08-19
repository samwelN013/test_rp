import time
from datetime import datetime
import pandas as pd
from pybit.unified_trading import HTTP
from pathlib import Path
# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
journal_folder = Path(__file__).resolve().parent/'_output_j'
journal_folder.mkdir(parents=True, exist_ok=True)
journal_path = journal_folder/'hyro_crypto_journal_back.csv'
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
    """Fetch total wallet balance converted to nominal USDT units."""
    try:
        response = session.get_wallet_balance(
            accountType="UNIFIED", coin="USDT")
        res = response["result"]["list"][0]
        total_usd = float(res.get("totalWalletBalance", 0.0))

        # Get USDT index conversion rate (usdValue / walletBalance)
        coins = res.get("coin", [])
        for c in coins:
            if c.get("coin") == "USDT":
                usd_val = float(c.get("usdValue", 0.0))
                wallet_bal = float(c.get("walletBalance", 0.0))

                if usd_val > 0 and wallet_bal > 0:
                    usdt_index_price = usd_val / wallet_bal
                    return round(total_usd / usdt_index_price, 4)

        return round(total_usd, 4)
    except Exception as e:
        print(f"Error fetching account balance: {e}")
    return 0.0


def get_entry_order_type_from_executions(symbol: str, start_time_ms: int) -> str:
    """Look up execution history to find exact entry orderType (Market vs Limit)."""
    try:
        response = session.get_executions(
            category="linear",
            symbol=symbol,
            startTime=start_time_ms - 5000,  # 5s margin before trade creation
            endTime=start_time_ms + 5000,
            limit=5
        )
        exec_list = response.get("result", {}).get("list", [])
        for execution in exec_list:
            if execution.get("orderType"):
                return execution.get("orderType")  # 'Market' or 'Limit'
    except Exception as e:
        print(f"Execution lookup error: {e}")
    return "Market"


def fetch_historical_closed_pnl(days_back: int = 550) -> list:
    """Fetch closed PnL history by looping backward in 7-day windows."""
    all_records = []

    # Calculate timestamps in milliseconds
    now_ms = int(time.time() * 1000)
    seven_days_ms = 7 * 24 * 60 * 60 * 1000
    cutoff_ms = now_ms - (days_back * 24 * 60 * 60 * 1000)

    current_end = now_ms

    while current_end > cutoff_ms:
        current_start = max(current_end - seven_days_ms, cutoff_ms)

        try:
            response = session.get_closed_pnl(
                category="linear",
                startTime=current_start,
                endTime=current_end,
                limit=100
            )
            records = response.get("result", {}).get("list", [])
            all_records.extend(records)

            # Move back to the next 7-day window
            current_end = current_start - 1
            time.sleep(0.1)  # Brief pause to respect API rate limits

        except Exception as e:
            print(f"Error fetching historical chunk: {e}")
            break

    # Deduplicate records by orderId / closedPnlId if any overlap
    seen_ids = set()
    unique_records = []
    for r in all_records:
        trade_id = r.get("orderId") or r.get("createdTime")
        if trade_id not in seen_ids:
            seen_ids.add(trade_id)
            unique_records.append(r)

    return unique_records

# def fetch_closed_trades():
#     """Fetch closed USDT Perpetual trades with simple backward balance tracking."""
#     current_balance = get_wallet_balance()

#     response = session.get_closed_pnl(category="linear", limit=50)
#     records = response.get("result", {}).get("list", [])

#     # Filter strictly for USDT Perpetual pairs
#     usdt_records = [t for t in records if t.get("symbol", "").endswith("USDT")]

#     # Sort chronologically (oldest first, newest last)
#     usdt_records.sort(key=lambda t: int(t.get("updatedTime", 0)))

#     # Step 1: Walk BACKWARD from current balance using the Net PnL (closedPnl) directly
#     running_balance = current_balance
#     historical_balances = []

#     for trade in reversed(usdt_records):
#         pnl = float(trade.get("closedPnl", 0.0))
#         historical_balances.append(round(running_balance, 4))
#         running_balance -= pnl  # Simply subtract the net PnL

#     # Reverse back to match chronological order (oldest -> newest)
#     historical_balances.reverse()

#     # Step 2: Build simple journal rows
#     journal_rows = []
#     for index, (trade, trade_balance) in enumerate(zip(usdt_records, historical_balances), start=1):
#         symbol = trade.get("symbol", "")
#         qty = float(trade.get("qty", 0.0))
#         entry_price = float(trade.get("avgEntryPrice", 0.0))
#         exit_price = float(trade.get("avgExitPrice", 0.0))
#         pnl = float(trade.get("closedPnl", 0.0))

#         created_time_ms = int(trade.get("createdTime", 0))
#         updated_time_ms = int(trade.get("updatedTime", 0))

#         entry_date = datetime.fromtimestamp(
#             created_time_ms / 1000) if created_time_ms else None
#         exit_date = datetime.fromtimestamp(
#             updated_time_ms / 1000) if updated_time_ms else None

#         days_in_trade = (
#             round((updated_time_ms - created_time_ms) / (1000 * 60 * 60 * 24), 2)
#             if (created_time_ms and updated_time_ms)
#             else 0.0
#         )

#         row = {
#             "trade number": index,
#             "symbol": symbol,
#             "side": "Long" if trade.get("side", "").lower() == "buy" else "Short",
#             "filled qty": qty,
#             "filled value (usdt)": round(qty * entry_price, 4),
#             "fill fee": round(float(trade.get("openFee", 0.0)), 6),
#             "exit fee": round(float(trade.get("closeFee", 0.0)), 6),
#             "avg fill price": entry_price,
#             "exit price": exit_price,
#             "PnL": round(pnl, 4),
#             "account balance": trade_balance,
#             "entry date": entry_date.strftime("%Y-%m-%d %H:%M:%S") if entry_date else "N/A",
#             "exit date": exit_date.strftime("%Y-%m-%d %H:%M:%S") if exit_date else "N/A",
#             "days in a trade": days_in_trade,
#             "order type entry": "Limit" if trade.get("execType") == "Trade" else "Market",
#             "order type exit": trade.get("orderType", "Market"),
#             "instrument": "USDT Perpetuals",
#         }
#         journal_rows.append(row)

#     return journal_rows


def export_to_csv(rows, filename=journal_path):
    if not rows:
        print("No trades found to write.")
        return

    df = pd.DataFrame(rows)
    try:
        df.to_csv(filename, index=False)
        print(
            f"Successfully exported {len(rows)} trades to '{filename.name}'!")
    except PermissionError:
        print(f'permsision denied: cannot write to {filename.name}'
              "\n please close the file if it's open in excel or other program")


if __name__ == "__main__":
    trades = fetch_historical_closed_pnl()
    export_to_csv(trades, journal_path)
