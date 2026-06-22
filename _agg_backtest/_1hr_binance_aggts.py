import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

BASE_URL = "https://api.binance.com/api/v3/aggTrades"
SYMBOL = "SOLUSDT"
LIMIT = 1000


def fetch_latest_aggtrades(symbol="SOLUSDT", limit=1000):
    params = {
        "symbol": symbol,
        "limit": limit
    }

    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()

    return response.json()


data = fetch_latest_aggtrades(SYMBOL, LIMIT)

df = pd.DataFrame(data)

print("\Raw Binance aggTrades columns:")
# print(df.columns.tolist())


print(df.head())

#  -- CSV DIRECTORY
# cwd =Path(__file__).resolve().parent
# filename = cwd/f"{SYMBOL}_aggtrades_raw.csv"
# df.to_csv(filename, index=False)

print()