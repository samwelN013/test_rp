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
    # api_key = "A33ksUVSWx55SmvkfE",
    # api_secret= "KhGyRe5nj4QqritCVpK2nCoVgI1MwHvYejkA",

)


def get_wallet_balance_1(metric: str = "totalWalletBalance") -> float:
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
# ====================================================================================
# the norminal value


def get_wallet_balance_hyro() -> float:
    """Fetch raw nominal USDT balance matching the Bybit/Hyrotrader UI."""
    try:
        response = session.get_wallet_balance(
            accountType="UNIFIED", coin="USDT")
        coins = response["result"]["list"][0].get("coin", [])
        for c in coins:
            if c.get("coin") == "USDT":
                return float(c.get("walletBalance", 0.0))
    except Exception as e:
        print(f"Error fetching account balance: {e}")
    return 0.0
# ===================================================================================
# DEMO NOMINAL VALUE


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
# ===========================================================================


current_bal = get_wallet_balance()
print(current_bal)
