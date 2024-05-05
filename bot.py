"""
Tradebot 

Websocket: Alpaca
Test Environment: API/ Paper Trade: Alpaca

1. look over trading logic and balance tracking in py_bot class - ie: create a function to alter and monitor balance

2. Create some constants for trade funds and RSI min and max 

3. Go over all precision handling 

4. Secure API keys using environment variables - look into more secure solutions before live deployment

5. Consider using cron expressions for scheduler

6. Need to start unit testing components of the bot and probe for unexpected behavior

7. Consider adding visualization elements to give perspective on the bots performance

8. Double check all logging files have timestamps 

9. From ChatGPT: While your code is clear, make sure to follow Python best practices 
and design patterns. This includes using meaningful variable and function names, 
adhering to PEP 8 conventions, and organizing code logically.

10. Screen for redundancy

11. Consider adding some docstring or a README to better detail functions

12. Add an automatic start - you should not be starting the script by pressing run (lmao) - all good tho

13. Consider adding cleanup operations before terminating the program 
        - For instance if you fail to sell at a stop loss because of an unexpected API error - should make sure position 
          is liquidated before exit. Otherwise you could face considerable unexpected losses. 

14. API calls to stocks and crpyto have different parameters consider altering the bot to work with both. 
        - This also entails altering the bot to work with short selling and longing

15. Need retry functionality for connection timeouts, if max retries occur and problem persists, just shut it down until further inspection.

16. Should add a separate library for strategies. 

IMO this is good work, but as we are just less than a week into development - it still needs to really be fleshed out. 
"""

from config import ALAPACA_PAPER_SECRET, ALPACA_LIVE_KEY, ALPACA_LIVE_SECRET, ALPACA_PAPER_KEY
from alpaca.trading.client import TradingClient
from alpaca.data import CryptoHistoricalDataClient
from alpaca.data.live.crypto import CryptoDataStream
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.common import APIError, RetryException
from decimal import Decimal
from indicators import rsi
from datetime import datetime, timezone
import logging
import pandas as pd
import asyncio
import time
from pytz import utc
import numpy as np
import pandas_ta as ta
from ta.volatility import average_true_range
from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException

bot = None
trade_client = None
transaction_log = None
api_log = None
crit_val = 1.96 # Based on confidence 

class OrderNotFilledError(Exception):
    pass

class OrderCancelledError(Exception):
    pass

class py_bot():
    def __init__(self, name, client, initial_balance, t_log, api_log):
        self.balance = initial_balance
        self.position = 0.0
        self.name = name
        self.key = ALPACA_PAPER_KEY
        self.secret = ALAPACA_PAPER_SECRET
        self.profit = 0.0
        self.client = client
        self.total_trades = 0
        self.dont_buy = False
        self.fees = Decimal(0.0)
        self.log = t_log
        self.api_log = api_log
        self.risk = 0.0
        self.sl_price = 0.0
        self.confirm_entry = False
        self.entry_price = 0.0
        self.initial_order = 0.0
        self.tp_counter = 0
    
    # Only buy a certain amount if I have enough in my acct balance to buy with 
    # Buy a certain quantity of a stock then log the transaction
    async def buy(self, asset, c_price, amount):   
        order_placed = False
        max_retry = 0

        # Prepare order
        data = MarketOrderRequest(
                symbol= asset,
                qty= amount,  
                side= OrderSide.BUY,
                type= 'market',
                time_in_force=TimeInForce.IOC,
            )

        while True:
            try:

                if self.balance - (amount*(c_price)) >= 0 and order_placed == False and max_retry <= 2:  # Place order if valid
                    order = self.client.submit_order(order_data= data)
                # Give it 5 seconds to fill then, if order has been filled, get qty
                time.sleep(10)
                check_order = self.client.get_order_by_id(order.id)

                if check_order.status == 'canceled':
                    max_retry = max_retry + 1
                    raise OrderCancelledError('Order Canceled Retrying purchase')
                
                order_placed = True

                print('Verifying Order\n')
                if check_order.filled_qty == '0':
                    raise OrderNotFilledError("Order not yet filled - Retrying order info request\n")
                print('Order Verified\n')   

                print('Checking Filled Position')
                check_position = self.client.get_open_position('ETHUSD') 

                amount_purchased = float(check_position.qty)

                # Update inital balance, profit, total trades and position
                self.balance = self.balance - amount_purchased*c_price
                print(f'Balance: {self.balance}')
                self.profit = self.profit - amount_purchased*c_price
                print(f'current profit: {self.profit}')
                self.position = self.position + amount_purchased
                print(f'updated pos: {self.position}')
                self.log.info(order)
                self.total_trades = self.total_trades + 1
                break
            except APIError as e:
                print(f'APIError: {e}  Time: {datetime.utcnow()}')
                self.api_log.info(e)
                print('Stopping Connection\n')
                raise SystemExit
            except RetryException as e:
                print(f'Retry: {e}  Time: {datetime.utcnow()}')
                self.api_log.info(e)
                break
            except (OrderNotFilledError, OrderCancelledError) as e:
                print(f'{e}  Time: {datetime.utcnow()}')
                self.api_log.info(e)
                await asyncio.sleep(10)

    # Only sell notional amount if I have that much worth to sell
    async def sell(self, asset, c_price, amount):
        print('Selling\n\n')
        data = MarketOrderRequest(
            symbol= asset,
            qty= amount,
            side= OrderSide.SELL,
            time_in_force= TimeInForce.IOC
        )

        # See if you can catch items in the API response to be treated as an exception (ie partial fill - 0 for fill price etc)
        # Raise exception when needed 
        # Figure out how to deal with partial fills - use Immediate or Close order

        if amount >= self.get_pos():
            # Place order
            order = self.client.submit_order(order_data=data)
            while True: 
                try:    
                    time.sleep(10)
                    check_order = self.client.get_order_by_id(order.id)

                    if check_order.status == 'canceled':
                        break

                    if check_order.filled_qty == '0':
                        raise OrderNotFilledError("Order not yet filled - Retrying request")
                    
                    print('Order Verified')

                    amount_sold = float(check_order.filled_qty) # comes out as 0.0 -> use filled average price
                    # Calculate fees, update total trades, position and profit
                    price_paid = c_price # Close enough since I am working with a market sell - using a limit I could be more exact
                    #fee_rate = Decimal('22.90') / Decimal('1000000')
                    #principal = Decimal(amount_purchased) * Decimal(price_paid)
                    #total_fees = ((principal*fee_rate) + (Decimal(amount_purchased)*Decimal('0.000119'))).quantize(Decimal('0.01'), rounding=ROUND_UP)
                    #self.fees = self.fees + total_fees
                    self.log.info(order)
                    self.total_trades = self.total_trades + 1
                    self.position = self.position - amount_sold
                    self.profit = self.profit + float(price_paid)*float(amount_sold)
                    print(f'current profit: {self.profit}')
                    break
                except APIError as e:
                    print(f'APIError: {e}  Time: {datetime.utcnow()}')
                    self.api_log.info(e)
                    print('Stopping Connection\n')
                    raise SystemExit
                except RetryException as e:
                    print(f'Retry: {e}  Time: {datetime.utcnow()}')
                    self.api_log.info(e)
                    break
                except OrderNotFilledError as e:
                    print(f'{e}  Time: {datetime.utcnow()}')
                    self.api_log.info(e)
                    await asyncio.sleep(10)
    
    def get_tp(self):
        return self.tp_counter
    
    def get_in(self):
        return self.initial_order

    def get_profit(self):
        return self.profit
    
    def get_pos(self):
        return self.position
    
    def get_risk(self):
        return self.risk
    
    def get_sl(self):
        return self.sl_price
    
    def get_ce(self):
        return self.confirm_entry
    
    def get_entry(self):
        return self.entry_price

    def set_sl(self, price):
        self.sl_price = price
    
    def set_risk(self, r_amt):
        self.risk = r_amt
    
    def set_entry(self, c_price):
        self.entry_price = c_price
    
    def set_in(self, order):
        self.initial_order = order
    
    def update_tp(self):
        self.tp_counter = self.tp_counter + 1
    
    def reset_tp(self):
        self.tp_counter = 0

    def flip_ce(self):
        self.confirm_entry = not self.confirm_entry
    
    

# Return a df of latest tiingo data for a given timeframe
def latest_data(symbol, start_date, end_date, freq, api_log):
    # For now we can just catch and log the error, in the future we will need to just handle each one differently 
    try:
        # First we need the latest 4 hour data from Tiingo
        client = CryptoHistoricalDataClient()

        params = CryptoBarsRequest(
            symbol_or_symbols=symbol,
            start=start_date,
            end=end_date, 
            timeframe=freq
            )
        
        quote = client.get_crypto_bars(params).df
    except (HTTPError, ConnectionError, Timeout, RequestException) as e:
        print(f'Error: {e}  Time: {datetime.utcnow()}')
        api_log.info(e)
        print('Stopping Connection\n')
        raise SystemExit
    
    df = quote.reset_index()
    selected_columns = ["timestamp", "close", "high", "low"] # will need to change the type of table generated based on what I were doing
    df = df[selected_columns]
    df = df.rename(columns={'timestamp':'date'})

    return df

def rsi_strategy(df, trade_bot, log, api_log):
    # Calculate current RSI over 14 day period (standard)
    signal = rsi.calculate_rsi(df, 14, False)
    signal = float(signal.iloc[0])
    
    # Will need to monitor for error types to check for 
    try:
        if signal <= 32.0 and trade_bot.get_db() == False:
            trade_bot.buy('ETH/USD', 1200, log)
            dont_buy = True
        elif signal >= 73.0 and trade_bot.get_db() == True:
            trade_bot.sell('ETH/USD', 1200, log)
            dont_buy = False
    except Exception as e:
        print(f'Exception: {e} Time: {datetime.utcnow()}')
        api_log.log(e)
        pass

async def mean_reversion_strategy(data, bot, api_log, trade_client):
    multiplier = 2.0 # Risk multiplier

    # Start time and frequency
    start_time = datetime(2023, 9, 4, 0, 0, 0, tzinfo=timezone.utc)
    time_frame = TimeFrame(5, TimeFrameUnit.Minute)

    df = latest_data('ETH/USD', start_time, datetime.utcnow(), time_frame, api_log) # pull latest thirty minute data

    # Calculate true range
    df['true_range'] = ta.true_range(df['high'], df['low'], df['close'])

    # Calculate drift based on log of percent change in price
    df['%Change'] = np.log(df['close'] / df['close'].shift(1))
    len_drift = 14 # periods to observe drift
    df['drift'] = df['%Change'].rolling(window=len_drift).mean() - (df['%Change'].rolling(window=len_drift).std() ** 2) * 0.5

    # true range wrong, atr f wrong, atr s wrong, std error wrong, t value wrong - or at least not close enough to trading view

    # separately compute t test and average true ranges - doing it in the loop with pandas is not suggested
    df['atr_f'] = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=5, mamode='rma')# average true range over last 5 bars
    df['atr_s'] = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=50, mamode='rma')# average true range over last 50 bars
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length= 14, mamode='rma')# average true range over last 14 bars
    df['sd'] = df['true_range'].rolling(window=5).std()
    df['t_val'] = (df['atr_f'] - df['atr_s']) / (df['sd'])# t test 

    current_low = df['low'].iloc[-1]
    current_atr = df['atr'].iloc[-1]
    c_price = df['close'].iloc[-1]

    print(df[['date', 'atr_f', 'atr_s', 'atr']].tail())

    # Perform t test and drift comparison to validate buy for next close
    tval = df['t_val'].iloc[-1]
    if abs(tval) > crit_val and df['drift'].iloc[-1] > df['drift'].iloc[-2] and bot.get_pos() == 0:
        print('entry is valid')
        bot.flip_ce()

    if bot.get_pos() > 0.0:
        print(f'updating stop : {max(bot.get_sl(), current_low - (current_atr*multiplier))}')
        bot.set_sl(max(bot.get_sl(), current_low - (current_atr*multiplier)))
    
    if bot.get_ce() == True and bot.get_pos() == 0:
        print('placing entry')
        bot.set_entry(float(c_price)) # set entry price
        bot.set_in(0.05*(4000 + bot.get_profit()) / float(c_price))
        bot.set_sl(current_low - current_atr*multiplier)
        print(f'initial stop loss: {current_low - current_atr*multiplier}')
        bot.set_risk(current_atr*multiplier)
        await bot.buy('ETH/USD', float(c_price), bot.get_in())
        bot.set_in(0.0)
        bot.flip_ce() # Need to reset entry confirmation 

    if float(c_price) <= bot.get_sl() and bot.get_pos() > 0.0:
        print(f'stop loss hit: {bot.get_sl()}')
        await bot.sell('ETH/USD', float(c_price), bot.get_pos())
        bot.set_sl(0.0)
        bot.set_entry(0.0)
        bot.set_risk(0.0)
        bot.reset_tp()
    
    # If the position is greater than 0 it should already be verified that the position was filled
    # Always use try except for API calls 
    if bot.get_pos() > 0.0:
        try:
            position = trade_client.get_open_position('ETHUSD')
            print(f'avg_entry: {position.avg_entry_price}')
            print(f'Average Entry: {position.avg_entry_price}')
            if bot.get_tp() <= 2 and float(c_price) > float(position.avg_entry_price):
                amt = np.floor(bot.get_pos() / 3.0) # Set the amount to sell
                if float(c_price) >= bot.get_entry() + bot.get_risk() and bot.get_tp() == 0:
                    print('taking profit lvl 1')
                    print(f'Amount: {amt}')
                    print(f'Current Pos: {bot.get_pos()}')
                    await bot.sell('ETH/USD', float(c_price), amt)
                    bot.update_tp()

                elif float(c_price) >= bot.get_entry() + bot.get_risk()*2.0 and bot.get_tp() == 1:
                    print('taking profit lvl 2')
                    await bot.sell('ETH/USD', c_price, amt)
                    bot.update_tp()
                
                elif float(c_price) >= bot.get_entry() + bot.get_risk()*3.0 and bot.get_tp() == 2:
                    print('taking profit lvl 3')
                    await bot.sell('ETH/USD', c_price, amt)
                    bot.reset_tp()
        except Exception as e:
            print(f'Exception: {e}')

async def handler(data):
    global bot 
    global trade_client
    global transaction_log
    global api_log
    
    if trade_client is None:
        trade_client = TradingClient(api_key=ALPACA_PAPER_KEY, secret_key=ALAPACA_PAPER_SECRET, paper=True)

    if transaction_log is None:
        transaction_log = logging.getLogger('transaction_log')
        transaction_log.setLevel(logging.INFO)
        trade_file_handler = logging.FileHandler('C:\\alpaca_client\\logs\\trades.log')
        trade_file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        trade_file_handler.setFormatter(trade_file_formatter)
        transaction_log.addHandler(trade_file_handler)
    
    if api_log is None:
        api_log = logging.getLogger('API')
        api_log.setLevel(logging.DEBUG)
        api_handler = logging.FileHandler('C:\\alpaca_client\\logs\\API.log')
        api_handler.setLevel(logging.DEBUG)
        api_log.addHandler(api_handler)
    
    if bot is None:
        bot = py_bot(name='botty', client=trade_client, initial_balance=4000.0, t_log=transaction_log, api_log=api_log)


    await mean_reversion_strategy(data=data, bot=bot, api_log=api_log, trade_client=trade_client)
    print(data.timestamp)    

def main():

    # Set up separate logs for transactions (complacency), alpaca and the scheduler -> they may need to be debugged separately
    scheduler_log = logging.getLogger('apscheduler')
    scheduler_log.setLevel(logging.DEBUG)
    sc_handler = logging.FileHandler('C:\\alpaca_client\\logs\\scheduler.log')
    sc_handler.setLevel(logging.DEBUG)
    scheduler_log.addHandler(sc_handler)

    try:
        stream_client = CryptoDataStream(api_key=ALPACA_LIVE_KEY, secret_key=ALPACA_LIVE_SECRET)
        stream_client.subscribe_bars(handler, 'ETH/USD')
        stream_client.run()
    except (KeyboardInterrupt, SystemExit):
        print('Process Terminated')
        stream_client.stop()
    except Exception as e:
        scheduler_log.log(f"Exception: {e}")

if __name__ == '__main__':
    main()