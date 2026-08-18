from datetime import datetime
import pandas as pd
from pybit.unified_trading import HTTP
from pathlib import Path

# test for wallet balance check
from pybit.unified_trading import HTTP
session = HTTP(
    testnet=False,
    demo=True,
    api_key="KtKADX3GIyPFbRItgj",
    api_secret="dvX94tGVd7wldCIXdjsPo6XEliNhGXaVluir",
)
bal = session.get_wallet_balance(
    accountType="UNIFIED",
    coin="USDT",)
df = pd.DataFrame(bal)

# FUNCTION 1


def get_wallet_balance_raw() -> float:
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


# FUNCTION 2; returns totalWalletBalance , usually converted to USD
def get_wallet_balance_real(metric: str = "totalWalletBalance") -> float:
    """
    Fetch current USDT balance from Bybit Unified Trading Account.

    :param metric: Options -> 'marginBalance', 'availableToWithdraw', 'walletBalance', or 'equity'
    :return: float balance
    """
    try:
        response = session.get_wallet_balance(
            accountType="UNIFIED", coin="USDT")
        account_list = response.get("result", {}).get("list", [])

        if account_list:
            # Check top-level account summary fields first
            if metric in account_list[0]:
                return float(account_list[0].get(metric, 0.0))

            # Look inside the coin array for coin-specific USDT values
            coins = account_list[0].get("coin", [])
            for c in coins:
                if c.get("coin") == "USDT":
                    # Available coin fields: 'walletBalance', 'equity', 'usdValue', 'unrealisedPnl'
                    return float(c.get(metric, c.get("totalWalletBalance", 0.0)))

    except Exception as e:
        print(f"Error fetching account balance: {e}")

    return 0.0

# FUNCTION 3


def get_wallet_balance() -> float:
    """Fetch exact USDT available/margin balance matching Bybit UI."""
    try:
        response = session.get_wallet_balance(
            accountType="UNIFIED", coin="USDT")
        account_list = response.get("result", {}).get("list", [])

        if account_list:
            coins = account_list[0].get("coin", [])
            for c in coins:
                if c.get("coin") == "USDT":
                    # Check availableToWithdraw or equity for exact USDT balance
                    available_to_withdraw = float(
                        c.get("availableToWithdraw", 0.0))
                    if available_to_withdraw > 0:
                        return round(available_to_withdraw, 4)

                    # Fallback to coin equity
                    return round(float(c.get("equity", 0.0)), 4)

    except Exception as e:
        print(f"Error fetching account balance: {e}")

    return 0.0


# FUNCTION 4
# to fetch order type history using historical 'order id'


def get_exact_order_type(symbol: str, order_id: str) -> str:
    """Fetch the exact order type (Market vs Limit) for a given order ID."""
    if not order_id:
        return "Unknown"

    try:
        response = session.get_order_history(
            category="linear",
            symbol=symbol,
            orderId=order_id,
            limit=1
        )
        orders = response.get("result", {}).get("list", [])
        if orders:
            # Bybit returns 'Market' or 'Limit'
            return orders[0].get("orderType", "Unknown")
    except Exception as e:
        print(f"Error fetching order history for {order_id}: {e}")

    return "Unknown"


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
        # Extract exact fill (open) fee and exit (close) fee directly from Bybit
        open_fee = float(trade.get("openFee", 0.0))
        close_fee = float(trade.get("closeFee", 0.0))

        # Fetch actual order IDs if available from the closed PnL record
        # Note: 'openOrderId' and 'closeOrderId' or 'orderId' exist depending on execution
        entry_order_id = trade.get("OrderId", "")
        # 'orderId' on closed PnL usually refers to exit order
        exit_order_id = trade.get("orderId", "")

        # Lookup exact order types from order history
        entry_order_type = get_exact_order_type(
            symbol, entry_order_id) if entry_order_id else "Market/Limit"
        exit_order_type = get_exact_order_type(
            symbol, exit_order_id) if exit_order_id else "Market/Limit"

        # Construct row matching your 17 exact columns
        row = {
            "trade number": index,
            "symbol": symbol,
            # Estimated taker/maker fee
            # "fill fee_est": float(trade.get("cumEntryValue", 0.0)) * 0.0006,
            # "exit fee_est": float(trade.get("cumExitValue", 0.0)) * 0.0006,
            # Actual taker/maker fee
            "fill fee": round(open_fee, 6),    # Exact entry fee paid
            "exit fee": round(close_fee, 6),   # Exact exit fee paid

            # "order type entry": trade.get("execType", "Market/Limit"),
            # "order type exit": "Market/Limit",

            "Entry ordertype": entry_order_type,
            "Exit ordertype": exit_order_type,
            # "instrument": "USDT Perpetuals",
        }
        journal_rows.append(row)

    return journal_rows


if __name__ == "__main__":
    trades = fetch_closed_trades()
    df = pd.DataFrame(trades)
    # print(df)
    current_balance = get_wallet_balance_real(metric="totalWalletBalance")
    print(current_balance)
