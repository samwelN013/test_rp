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

# TO RENAMES COLUMNS OF THE DATAFRAME -----------------------------------------------------
df = df.rename(columns={'a': 'agg_trade_id',
                        'p': 'price',
                        'q': 'quantity',
                        'f': 'first_trade_id',
                        'l': 'last_trade_id',
                        'T': 'transact_time',
                        'm': 'is_buyer_maker',
                        'M': 'ignore'})

# # ------- RE-ORDERING COLUMNS -----------------------------------------------------------
custom_order = ['transact_time', 'price', 'quantity', 'is_buyer_maker',
                'agg_trade_id', 'first_trade_id', 'last_trade_id', 'ignore']

# df = df[custom_order]
# -------------------------------------------------------- OR
# df = df.reindex(sorted(df.columns), axis=1)
# -------------------------------------------------------- OR
# df = df.reindex(columns=['transact_time', 'price', 'quantity', 'is_buyer_maker',
#                          'agg_trade_id', 'first_trade_id', 'last_trade_id', 'ignore'])
# -------------------------------------------------------- OR
df = df.reindex(columns=custom_order)

# ------ CALLING THE DATAFRAME -------------------------

# print(df.columns.tolist())  # prints column headings
print(df.head())
# print(df.tail())
# print(df[0:100].to_string())
# print(df[-20:])

# ------------- NEW DF --------------


# # -- CSV DIRECTORY
# cwd =Path(__file__).resolve().parent
# filename = cwd.parent/'_output'/f"{SYMBOL}_aggtrades_raw.csv"
# df.to_csv(filename, index=False)
