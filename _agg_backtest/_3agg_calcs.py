import pandas as pd
import numpy as np
from pathlib import Path
from binance.client import Client
from matplotlib import pyplot as plt
import csv

# import aggtrades
cwd = Path(__file__).resolve()
file_path = cwd.parent/'__input_ag'/'SOLUSDT-aggTrades-2026-06-20.csv'
# symbol name
SYMBOL = file_path.name.split("-")[0]
file_output_path = cwd.parent/'__output_ag'/f"{SYMBOL}_ouput_sample.csv"
# file_output_path = cwd.parent/'__output_ag'/f"{SYMBOL}_ouput_sample.parquet"

# coin stats like average volume from BINANCE


def get_binance_coin_stats(SYMBOL):
    """ fetches coin stats like average volume from BINANCE """
    try:
        client = Client()
        klines = client.futures_klines(symbol=SYMBOL, interval='1d', limit=21)
        closed_klines = klines[:-1]  # Exclude today's incomplete candle
        # Index 4: Close Price, Index 5: Volume
        volumes = [float(k[5]) for k in closed_klines]
        prices = [float(k[4]) for k in closed_klines]
        # ---------------------------------
        vol_20_ma = sum(volumes[-20:]) / 20
        price_20_ma = sum(prices[-20:]) / 20
        notional_vol_ma = vol_20_ma * price_20_ma
        # print(vol_20_ma)
        return vol_20_ma, price_20_ma, notional_vol_ma
    except Exception as e:
        print(f"BINANCE API error for {SYMBOL}: {e}")
        return None, None, None


def aggregated_data():
    v_ma, p_ma, notional_ma = get_binance_coin_stats(SYMBOL)
    # to stop the program incase notional_ma is not available or 0
    if not notional_ma:
        return

    # load csv to df
    df = pd.read_csv(file_path)

    # rename columns

    # df = df.rename(columns={'a': 'agg_tde_id', 'p': 'price', 'q': 'base_qty',
    #                         'f': 'first_tde_id', 'l': 'last_tde_id',
    #                         'T': 'transact_time', 'm': 'is_buyer_maker', 'M': 'ignore'})
    df = df.rename(columns={'agg_trade_id': 'agg_tde_id', 'quantity': 'base_qty',
                            'first_trade_id': 'first_tde_id', 'last_trade_id': 'last_tde_id'
                            })

    # format some columns -- keep time as datetime , not string for GROUPING
    # .dt.strftime("%Y-%m-%d %H:%M:%S")
    df['transact_time'] = pd.to_datetime(df['transact_time'], unit='ms')
    # helper columns
    df['quote_qty_usdt'] = df['price'] * df['base_qty']
    df['buy_vol_usdt'] = np.where(
        df['is_buyer_maker'] == False, df['quote_qty_usdt'], 0.0)
    df['sell_vol_usdt'] = np.where(
        df['is_buyer_maker'] == True, df['quote_qty_usdt'], 0.0)

    # BUCKETING TIME WINDOWS --- groupby --- aggregating
    bdf = df.groupby(pd.Grouper(key='transact_time', freq='5Min')).agg(tde1_price=('price', 'first'),
                                                                       last_price=(
        'price', 'last'),
        buyVol_usdt=(
        'buy_vol_usdt', 'sum'),
        sellVol_usdt=(
        'sell_vol_usdt', 'sum')
    ).reset_index()
    # rename columns
    bdf = bdf.rename(columns={'transact_time': 'time'})
    # derived columns
    bdf['delta'] = bdf['buyVol_usdt'] - bdf['sellVol_usdt']
    bdf['prc_%change_window'] = (
        bdf['last_price']-bdf['tde1_price'])/bdf['tde1_price']
    day_open_price = bdf['tde1_price'].iloc[0]
    bdf['dayOpen_prc%change'] = (
        bdf['last_price'] - day_open_price)/day_open_price

    # column naming convention
    # 1 time = the time duration of the stamp
    # 2 tde1_price = the first trade price in the time window
    # 3 last_price = the price of the last trade in the time window
    # 4 buyVol_usdt = aggressive buy volume in usdt
    # 5 delta
    # 6 sellVol_usdt = aggressive sell volume in usdt
    # 7 prc_%change_window = the price percetange change in time window
    # 8 dayOpen_prc%change = is the overall price percentage change from day open

    # ----------COLUMN FORMATING ------------------------
    bdf['delta'] = bdf['delta'].round(2)
    bdf['buyVol_usdt'] = bdf['buyVol_usdt'].round(2)
    bdf['sellVol_usdt'] = bdf['sellVol_usdt'].round(2)

    # ------------- EXPORTING dataframe to CSV FILE using pandas ---------------
    # bdf.to_csv(file_output_path, index=False)

    # ------------- EXPORTING the dataframe to parquet using pandas ---------------
    # bdf.to_parquet(file_output_path)

    return bdf


def main():

    bdf = aggregated_data()

    print(bdf.tail())

    # ------------ GRAPHS ANALYSIS  -------------------------------
    plt.plot(bdf['time'], bdf['buyVol_usdt'],
             color='green', label="aggressive buy volume")
    plt.plot(bdf['time'], bdf['sellVol_usdt'],
             color='red', label="aggressive sell volume")
    plt.title("volumes against time")
    plt.xlabel("time to the day")
    plt.ylabel('volumes')
    plt.grid()
    plt.legend()
    plt.show()


if __name__ == "__main__":
    main()
