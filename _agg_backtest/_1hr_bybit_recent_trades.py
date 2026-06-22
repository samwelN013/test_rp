import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

# Bybit V5 API endpoint for recent public trades
BASE_URL = "https://api.bybit.com/v5/market/recent-trade"
CATEGORY = "linear"  # 'linear' is used for USDT perpetual contracts
SYMBOL = "SOLUSDT"
LIMIT = 1000         # Max limit is 1000 for linear/derivatives (60 for spot)

def fetch_latest_trades(category="linear", symbol="SOLUSDT", limit=1000):
    params = {
        "category": category,
        "symbol": symbol,
        "limit": limit
    }

    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    
    json_data = response.json()
    
    # Ensure the API request was successful (retCode 0 means success)
    if json_data.get("retCode") != 0:
        raise Exception(f"Bybit API Error: {json_data.get('retMsg')}")

    # Bybit wraps the actual trades array inside result -> list
    return json_data["result"]["list"]

data = fetch_latest_trades(CATEGORY, SYMBOL, LIMIT)

df = pd.DataFrame(data)

print("\nRaw Bybit public trades columns:")
# print(df.columns.tolist())

print(df.head())

# # -- CSV DIRECTORY
# cwd = Path(__file__).resolve().parent
# filename = cwd.parent / '_output' / f"{SYMBOL}_bybit_trades_raw.csv"
# df.to_csv(filename, index=False)