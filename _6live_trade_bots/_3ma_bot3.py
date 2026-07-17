from pybit.unified_trading import HTTP, WebSocket
import pandas as pd
import numpy as np
import time

class BybitTradingBot:
    def __init__(self, api_key, api_secret, symbol, quantity, timeframe="1"):
        """
        The constructor method. This acts as the setup hub for your bot instance.
        Any variable attached to 'self' can be accessed anywhere inside this class.
        """
        # Strategy Parameters
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbol = symbol
        self.coin_qty = quantity
        self.timeframe = timeframe
        
        # State Tracking Variables (Fully protected from global scope leaks)
        self.current_position = "None"  # Track if we are currently "Long", "Short", or "None"
        self.candles_df = pd.DataFrame() # Storage for historic and streaming candles
        
        # Initialize Bybit HTTP Session for orders and historical data
        self.session = HTTP(
            testnet=False,
            demo=True,
            api_key=self.api_key,
            api_secret=self.api_secret,
        )
        
    # =========================================================================
    # METHOD GROUP 1: ORDER EXECUTION HANDLERS
    # =========================================================================
    
    def enter_trade(self, side):
        """Places an instant market order for either 'Buy' (Long) or 'Sell' (Short)"""
        try:
            # Generate a unique tracking label using a clean micro-timestamp
            order_link_id = f"bot-{side.lower()}-{int(time.time() * 1000)}"
            
            open_td = self.session.place_order(
                category="linear",
                symbol=self.symbol,
                side=side,
                orderType="Market",
                qty=self.coin_qty,
                timeInForce="GTC",
                orderLinkId=order_link_id
            )
            print(f"🔥 [{side} TRADE PLACED] Instant position of {self.coin_qty} {self.symbol} taken.")
            return open_td
        except Exception as e:
            print(f"❌ Error entering trade: {e}")

    def exit_trade(self):
        """Closes out all open contracts for the tracked symbol using reduceOnly=True"""
        try:
            close_td = self.session.place_order(
                category="linear",
                symbol=self.symbol,
                side="Sell",  # Default placeholder; Bybit resolves the actual close direction automatically
                orderType="Market",
                qty="0",
                reduceOnly=True,
                closeOnTrigger=True,
                timeInForce="GTC"
            )
            print(f"🛑 [POSITION EXITED] All market entries for {self.symbol} closed via reduceOnly.")
            return close_td
        except Exception as e:
            print(f"❌ Error exiting trade: {e}")

    # =========================================================================
    # METHOD GROUP 2: MATHEMATICAL MATH ENGINE (TECHNICAL INDICATORS)
    # =========================================================================

    def _calculate_wma(self, series, period):
        """Calculates Weighted Moving Average. (Internal helper method, denoted by _)"""
        weights = np.arange(1, period + 1)
        return series.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

    def _calculate_hma(self, series, period):
        """Calculates Hull Moving Average (WMA of half period - WMA of full period)"""
        half_period = int(period / 2)
        sqrt_period = int(np.sqrt(period))
        
        wma_half = self._calculate_wma(series, half_period)
        wma_full = self._calculate_wma(series, period)
        
        raw_hma = (2 * wma_half) - wma_full
        hma = self._calculate_wma(raw_hma, sqrt_period)
        return hma

    def process_technical_indicators(self):
        """Calculates live moving averages and evaluates trade condition crossovers"""
        # Ensure we have at least 200 items in our dataframe before attempting calculations
        if len(self.candles_df) < 200:
            return
            
        # Calculate standard Simple Moving Averages (MA)
        self.candles_df['ma65'] = self.candles_df['close'].rolling(window=65).mean()
        self.candles_df['ma200'] = self.candles_df['close'].rolling(window=200).mean()
        
        # Calculate the specialized Hull Moving Average (HMA 65)
        self.candles_df['hma65'] = self._calculate_hma(self.candles_df['close'], 65)
        
        # Extract previous row and current row to identify crossover moments
        prev_row = self.candles_df.iloc[-2]
        curr_row = self.candles_df.iloc[-1]
        
        price = curr_row['close']
        ma200 = curr_row['ma200']
        
        hma65_prev = prev_row['hma65']
        ma65_prev = prev_row['ma65']
        hma65_curr = curr_row['hma65']
        ma65_curr = curr_row['ma65']
        
        # Boolean tracking logic to capture crossovers clearly
        cross_up = (hma65_prev <= ma65_prev) and (hma65_curr > ma65_curr)
        cross_down = (hma65_prev >= ma65_prev) and (hma65_curr < ma65_curr)
        
        print(f"📊 Live Scan ({self.timeframe}m) | Price: {price:.2f} | MA200: {ma200:.2f} | HMA65: {hma65_curr:.2f} | MA65: {ma65_curr:.2f}")
        
        # --- STRATEGY CROSSOVER IMPLEMENTATION ---
        
        # BULL MARKET CONDITION (Price is trading above the baseline MA 200)
        if ma200 < price:
            if cross_up and self.current_position != "Long":
                print("🚀 CRITERIA MET: Price above MA200 & HMA65 Crossed UP over MA65!")
                if self.current_position == "Short":
                    self.exit_trade()
                self.enter_trade(side="Buy")
                self.current_position = "Long"
                
            elif cross_down and self.current_position == "Long":
                print("📉 EXIT CRITERIA MET: HMA65 Crossed DOWN over MA65 in Bull Market.")
                self.exit_trade()
                self.current_position = "None"
                
        # BEAR MARKET CONDITION (Price is trading below the baseline MA 200)
        elif ma200 > price:
            if cross_down and self.current_position != "Short":
                print("🩸 CRITERIA MET: Price below MA200 & HMA65 Crossed DOWN under MA65!")
                if self.current_position == "Long":
                    self.exit_trade()
                self.enter_trade(side="Sell")
                self.current_position = "Short"
                
            elif cross_up and self.current_position == "Short":
                print("🚀 EXIT CRITERIA MET: HMA65 Crossed UP over MA65 in Bear Market.")
                self.exit_trade()
                self.current_position = "None"

    # =========================================================================
    # METHOD GROUP 3: CONNECTIONS AND DATA FEEDS (REST & WEBSOCKET)
    # =========================================================================

    def fetch_historical_candles(self):
        """Queries Bybit via HTTP to pull the preceding 200 candles before starting live feed"""
        print(f"📥 Loading initial 200 candles via HTTP for {self.symbol} on {self.timeframe}m timeframe...")
        
        response = self.session.get_kline(
            category="linear",
            symbol=self.symbol,
            interval=self.timeframe,
            limit=200
        )
        
        raw_list = response.get("result", {}).get("list", [])
        raw_list.reverse() # Sort chronologically (oldest to newest)
        
        data_processed = []
        for candle in raw_list:
            data_processed.append({
                "timestamp": int(candle[0]),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4])
            })
            
        self.candles_df = pd.DataFrame(data_processed)
        print("✅ Cold start initialized. Historical dataframe populated cleanly.")

    def handle_live_kline(self, message):
        """Callback engine assigned to manage incoming live data rows from the WebSocket pipe"""
        candle_data = message.get("data", [])
        if not candle_data:
            return
            
        candle = candle_data[0]
        timestamp = int(candle.get("start"))
        close_price = float(candle.get("close"))
        
        # If the incoming candle timestamp is already present, update its ticking close value
        if timestamp in self.candles_df["timestamp"].values:
            self.candles_df.loc[self.candles_df["timestamp"] == timestamp, "close"] = close_price
        else:
            # If a new time period starts, append a clean row to our dataset
            new_row = pd.DataFrame([{
                "timestamp": timestamp,
                "open": float(candle.get("open")),
                "high": float(candle.get("high")),
                "low": float(candle.get("low")),
                "close": close_price
            }])
            self.candles_df = pd.concat([self.candles_df, new_row], ignore_index=True)
            
        # Memory cleanup buffer: keep exactly 205 items to protect compute speed
        if len(self.candles_df) > 205:
            self.candles_df = self.candles_df.iloc[-205:].reset_index(drop=True)
            
        # Re-verify and recalculate system metrics on every tick updates
        self.process_technical_indicators()

    def start_bot(self):
        """Spawns the long-running live market stream framework"""
        # Step 1: Pre-populate historic data context
        self.fetch_historical_candles()
        
        # Step 2: Formulate Public Linear network streaming channel
        print(f"🔌 Spawning Live WebSocket Stream Connection for {self.symbol}...")
        ws = WebSocket(
            testnet=False, 
            channel_type="linear"
        )
        
        # Step 3: Map our inner handler directly into the incoming stream pipe
        # The WebSocket library expects integers for pure numeric strings like "5"
        ws.kline_stream(
            interval=int(self.timeframe) if self.timeframe.isdigit() else self.timeframe,
            symbol=self.symbol,
            callback=self.handle_live_kline
        )
        
        print(f"🤖 Bot Instance fully active. Monitoring {self.timeframe}m crossovers. Use Ctrl+C to terminate.")
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down bot safely...")
                break


# =========================================================================
# SYSTEM TRIGGER BLOCK
# =========================================================================
if __name__ == "__main__":
    # Setup values matching your original variables layout
    API_KEY = "XF0cj2YhDr1pJ6IbrT"
    API_SECRET = "JUtzwBKUfDT6BskYLtT12dQCZ9C7DG395OBh"
    
    watchlist = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "TAOUSDT", "ADAUSDT", "BNBUSDT", "WLDUSDT", "XRPUSDT", "DOGEUSDT", "XAUUSDT"]
    watch_qty = {'BTCUSDT': 0.03, 'ETHUSDT': 1, 'SOLUSDT': 10, 'TAOUSDT': 5, 'ADAUSDT': 5000, 'BNBUSDT': 3, 'WLDUSDT': 5000, 'XRPUSDT': 1000, 'DOGEUSDT': 12000, 'XAUUSDT': 1}

    CHOSEN_SYMBOL = watchlist[6]              # TAOUSDT
    CHOSEN_QUANTITY = watch_qty[CHOSEN_SYMBOL] # 5
    CHOSEN_TIMEFRAME = "13"                    # Timeframe can easily be shifted ("1", "5", "15", "60")

    # Instantiate the class object with parameters
    bot = BybitTradingBot(
        api_key=API_KEY,
        api_secret=API_SECRET,
        symbol=CHOSEN_SYMBOL,
        quantity=CHOSEN_QUANTITY,
        timeframe=CHOSEN_TIMEFRAME
    )
    
    # Fire up the engine!
    bot.start_bot()