from datetime import datetime
import pandas as pd
from pybit.unified_trading import HTTP
from pathlib import Path
import time
# loading the env
from dotenv import load_dotenv
import os

# THE TRADING JOURNAL FOR HYROTRADER CHALLENGE

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
journal_folder = Path(__file__).resolve().parent/'real_trade_journals'
# ensures the folder is there
journal_folder.mkdir(parents=True, exist_ok=True)
journal_path = journal_folder/'Hyro_trades_journal_sam.csv'
#  API credentials:

env_file = Path(__file__).resolve().parent/'_input_j'/'trade.env'

load_dotenv(env_file)
# Read environment variables


API_KEY: str = os.getenv("hyro_api_key")
API_SECRET: str = os.getenv("hyro_api_secret")

# safety check: Ensure keys were actually loaded
if not API_KEY or not API_SECRET:
    raise ValueError(
        "API credentials missing ! Ensure api keys are in the .env file")

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


def fetch_closed_trades(days_back: int = 7) -> list:
    """
    Fetch closed USDT Perpetual trades over a flexible historical window (`days_back`)
    and reconstruct exact row-by-row historical account balances.

    :param days_back: Number of past days to query (e.g., 365 for May 2025, 7 for quick updates)
    """
    latest_balance = get_wallet_balance()

    # 1. Calculate time windows in milliseconds
    now_ms = int(time.time() * 1000)
    seven_days_ms = 7 * 24 * 60 * 60 * 1000
    cutoff_ms = now_ms - (days_back * 24 * 60 * 60 * 1000)

    raw_records = []
    current_end = now_ms

    # 2. Loop backward in 7-day chunks (Bybit API requirement)
    while current_end > cutoff_ms:
        current_start = max(current_end - seven_days_ms, cutoff_ms)
        try:
            response = session.get_closed_pnl(
                category="linear",
                startTime=current_start,
                endTime=current_end,
                limit=100
            )
            chunk = response.get("result", {}).get("list", [])
            raw_records.extend(chunk)

            # Move window backward
            current_end = current_start - 1
            time.sleep(0.05)  # Tiny pause to respect API rate limits
        except Exception as e:
            print(f"Error fetching historical chunk: {e}")
            break

    # 3. Deduplicate raw records & filter for USDT symbols
    seen_ids = set()
    usdt_records = []
    for t in raw_records:
        trade_id = t.get("orderId") or t.get("createdTime")
        symbol = t.get("symbol", "")
        if trade_id not in seen_ids and symbol.endswith("USDT"):
            seen_ids.add(trade_id)
            usdt_records.append(t)

    # Return early if no trades were found
    if not usdt_records:
        print(f"No trades found in the past {days_back} days.")
        return []

    # 4. Sort chronologically (oldest first, newest last)
    usdt_records.sort(key=lambda t: int(t.get("updatedTime", 0)))

    # 5. Work BACKWARD from latest_balance to reconstruct row balances
    running_balance = latest_balance
    historical_balances = []

    for trade in reversed(usdt_records):
        pnl = float(trade.get("closedPnl", 0.0))
        historical_balances.append(round(running_balance, 4))
        running_balance -= pnl  # Subtract net PnL step-by-step

    # Reverse historical_balances back to match chronological order (oldest -> newest)
    historical_balances.reverse()

    # 6. Build the final journal rows in your clean 17-column format
    journal_rows = []
    for index, (trade, trade_balance) in enumerate(zip(usdt_records, historical_balances), start=1):
        symbol = trade.get("symbol", "")
        qty = float(trade.get("qty", 0.0))
        entry_price = float(trade.get("avgEntryPrice", 0.0))
        exit_price = float(trade.get("avgExitPrice", 0.0))
        pnl = float(trade.get("closedPnl", 0.0))

        filled_value = (qty * entry_price)
        percent_pnl = (pnl/filled_value)*100
        cumm_pnl = (trade_balance-10000)

        created_time_ms = int(trade.get("createdTime", 0))
        updated_time_ms = int(trade.get("updatedTime", 0))

        entry_date = datetime.fromtimestamp(
            created_time_ms / 1000) if created_time_ms else None
        exit_date = datetime.fromtimestamp(
            updated_time_ms / 1000) if updated_time_ms else None

        days_in_trade = (
            round((updated_time_ms - created_time_ms) / (1000 * 60 * 60 * 24), 2)
            if (created_time_ms and updated_time_ms)
            else 0.0
        )

        row = {
            "trade number": index,
            "symbol": symbol,
            "side": "Long" if trade.get("side", "").lower() == "buy" else "Short",
            "filled value (usdt)": round(qty * entry_price, 4),
            "filled qty": qty,

            "avg fill price": entry_price,
            "exit price": exit_price,

            "fill fee": round(float(trade.get("openFee", 0.0)), 6),
            "exit fee": round(float(trade.get("closeFee", 0.0)), 6),

            "Net PnL": round(pnl, 4),
            "% net pnl": f"{round(percent_pnl, 2)} %",
            "cumm net pnl": round(cumm_pnl, 2),

            "account balance": trade_balance,
            "entry date": entry_date.strftime("%Y-%m-%d %H:%M:%S") if entry_date else "N/A",
            "exit date": exit_date.strftime("%Y-%m-%d %H:%M:%S") if exit_date else "N/A",
            "days in a trade": days_in_trade,

            # "Entry order type": trade.get("orderType", "Market"),
            # "Exit order type": "Limit" if trade.get("execType") == "Trade" else "Market",

            # "instrument": "USDT Perpetuals",
        }
        journal_rows.append(row)

    return journal_rows


def export_to_csv(rows, filename=journal_path):
    """
    Export trades to CSV. Creates the file if it doesn't exist, 
    or appends only new, non-duplicate trades if it already exists.
    """
    if not rows:
        print("No trades found to write.")
        return

    new_df = pd.DataFrame(rows)

    # Check if the journal already exists
    if filename.exists() and filename.stat().st_size > 0:
        try:
            existing_df = pd.read_csv(filename)

            # Create a unique composite key (symbol + exit date) to identify duplicates
            # (Matches trade exit precision down to the second)
            existing_keys = set(
                existing_df["symbol"].astype(
                    str) + "_" + existing_df["exit date"].astype(str)
            )

            new_df["unique_key"] = new_df["symbol"].astype(
                str) + "_" + new_df["exit date"].astype(str)

            # Filter for rows that DO NOT exist in the current file
            filtered_df = new_df[~new_df["unique_key"].isin(
                existing_keys)].drop(columns=["unique_key"])

            if filtered_df.empty:
                print("Journal is up to date! No new trades to append.")
                return

            # Combine existing trades with newly fetched trades
            combined_df = pd.concat(
                [existing_df, filtered_df], ignore_index=True)

            # Re-index 'trade number' sequentially (1, 2, 3...)
            combined_df["trade number"] = range(1, len(combined_df) + 1)

            # Save updated DataFrame back to file
            combined_df.to_csv(filename, index=False)
            print(
                f"Appended {len(filtered_df)} new trade(s) to '{filename.name}'! (Total trades: {len(combined_df)})")

        except PermissionError:
            print(
                f"[Permission Error] Cannot write to '{filename.name}'.\n"
                "Please close the file in Excel/VS Code preview and run again."
            )
        except Exception as e:
            print(f"Error reading/appending to existing journal: {e}")

    else:
        # File doesn't exist yet: write fresh CSV
        try:
            new_df.to_csv(filename, index=False)
            print(
                f"Created new journal! Exported {len(rows)} trades to '{filename.name}'.")
        except PermissionError:
            print(
                f"[Permission Error] Cannot write to '{filename.name}'.\n"
                "Please close the file in Excel/VS Code preview and run again."
            )


if __name__ == "__main__":
    trades = fetch_closed_trades()
    export_to_csv(trades, journal_path)
