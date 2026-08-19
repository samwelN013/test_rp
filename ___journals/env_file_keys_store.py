from datetime import datetime
import pandas as pd
from pybit.unified_trading import HTTP
from pathlib import Path
# loading the env
from dotenv import load_dotenv
import os

# STEP 1 . Install a python-dotenv package
# pip install python-dotenv

# 2. STEP 2: CREATE .env file and load in your credintials
#.env location
env_file =Path(__file__).resolve().parent/'_input_j'/'trade.env'

load_dotenv(env_file)
# Read environment variables
API_KEY: str = os.getenv("bybit_m_demo_api_key")
API_SECRET: str = os.getenv("bybit_m_demo_api_secret")

# safety check: Ensure keys were actually loaded
if not API_KEY or not API_SECRET:
    raise ValueError(
        "API credentials missing ! Ensure api keys are in the .env file")

# Initialize Bybit HTTP Session safely
session = HTTP(
    testnet=False,
    demo=True,
    api_key=API_KEY,
    api_secret=API_SECRET,
)


# def get_wallet_balance() -> float:
#     """Fetch total wallet balance converted to nominal USDT units."""
#     try:
#         response = session.get_wallet_balance(
#             accountType="UNIFIED", coin="USDT")
#         res = response["result"]["list"][0]
#         total_usd = float(res.get("totalWalletBalance", 0.0))

#         # Get USDT index conversion rate (usdValue / walletBalance)
#         coins = res.get("coin", [])
#         for c in coins:
#             if c.get("coin") == "USDT":
#                 usd_val = float(c.get("usdValue", 0.0))
#                 wallet_bal = float(c.get("walletBalance", 0.0))

#                 if usd_val > 0 and wallet_bal > 0:
#                     usdt_index_price = usd_val / wallet_bal
#                     return round(total_usd / usdt_index_price, 4)

#         return round(total_usd, 4)
#     except Exception as e:
#         print(f"Error fetching account balance: {e}")
#     return 0.0

# accountBal =get_wallet_balance()
# print(accountBal)
