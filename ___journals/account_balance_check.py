import pandas as pd
from pybit.unified_trading import HTTP

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
df =pd.DataFrame(bal)

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

if __name__ == "__main__":
    print(get_wallet_balance())

