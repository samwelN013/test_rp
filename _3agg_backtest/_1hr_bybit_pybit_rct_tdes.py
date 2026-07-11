import pandas as pd
from datetime import datetime
from pathlib import Path
from pybit.unified_trading import HTTP

SYMBOL = "SOLUSDT"
LIMIT = 1000

def fetch_latest_trades_pybit(symbol="SOLUSDT", limit=1000):
    # Initialize an unauthenticated HTTP session for public market data
    session = HTTP(testnet=False)
    
    # Call the get_public_trades endpoint (v5/market/recent-trade)
    # Corrected: Added the "s" to get_public_trades
    response = session.get_public_trade_history(
        category="linear",
        symbol=symbol,
        limit=limit
    )
    
    # pybit automatically checks for API errors and raises exceptions if retCode != 0
    return response["result"]["list"]

data = fetch_latest_trades_pybit(SYMBOL, LIMIT)

df = pd.DataFrame(data)

print("\nRaw Bybit public trades columns via pybit:")
# print(df.columns.tolist())

print(df[0:100].to_string())

# # -- CSV DIRECTORY
# cwd = Path(__file__).resolve().parent
# filename = cwd.parent / '_output' / f"{SYMBOL}_bybit_trades_raw.csv"
# df.to_csv(filename, index=False)