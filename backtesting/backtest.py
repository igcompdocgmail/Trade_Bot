import sys
sys.path.append('C:\\alpaca_client')
from bot import py_bot
from tiingo import TiingoClient
from decimal import Decimal, ROUND_UP, getcontext # need this for precision in transactions
from datetime import datetime, timezone
import matplotlib.pyplot as plt
from ta.volatility import average_true_range
from indicators import macd, rsi
from bot import latest_data
from alpaca.trading.client import TradingClient
from config import ALPACA_PAPER_KEY, ALAPACA_PAPER_SECRET, TIINGO_KEY
import pandas as pd
import pandas_ta as ta
import numpy as np
import logging
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit


def plot_backtest(data, buy, sell, stop_loss):
    # Trim the date and set as the index
    data.set_index('date', inplace=True)

    plt.figure(figsize=(30,10))
    # Plot closing prices
    plt.plot(data.index, data['close'], label='Closing Prices', color='black')

    #Plot buy and sell points
    plt.scatter(buy, data.loc[buy, 'close'], c='g', marker='^', label="Buy", s=60)
    plt.scatter(sell, data.loc[sell, 'close'], c='b', marker='v', label="Sell", s=60)
    plt.scatter(stop_loss, data.loc[stop_loss, 'sl_price'], c='r', marker='v', label='Stop Loss', s=60)

    plt.title('Back Test')
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.legend()
    plt.show()

def mean_reversion_test(stop_loss, risk, rej_nhypothesis, confirmed_entry,
          net_profit, sl_price, df, current_pos, buy, sell, crit_val):
    balance = 2000
    tp_counter = 0
    profitable_trades = 0
    for index in df.index:  
        if index > 1:
            c_high = df.loc[index, 'high']
            c_low = df.loc[index, 'low']
            c_current = df.loc[index, 'close']

            # update the position if still holding
            if current_pos > 0.0:
                sl_price = max(sl_price, c_low - (df.loc[index, 'atr'])*2.0)

            # Entry if no position yet 
            if confirmed_entry and current_pos == 0:
                # Determines how much to buy on each triggered long based on equity
                # Cab change initial order size later to account for equity - not necessary if only trading one asset
            
                initial_entry_price = c_current
                initial_order_size = (0.05*(2000 + net_profit)) / (initial_entry_price)
                if (balance - initial_order_size * initial_entry_price > 0):
                    balance = balance - (initial_order_size * initial_entry_price)
                    current_pos = current_pos + initial_order_size
                    sl_price = c_low - (df.loc[index, 'atr']*2.0)
                    risk = (df.loc[index, 'atr']*2.0)
                    buy.append(df.loc[index, 'date'])
                
            
            # If stop loss is triggered we sell and restart the process
            if c_high >= sl_price >= c_low and current_pos > 0.0:
                stop_loss.append(df.loc[index, 'date'])
                df.loc[index, 'sl_price'] = sl_price
                balance = balance + current_pos*sl_price
                if sl_price > initial_entry_price:
                    profitable_trades = profitable_trades + 1
                    net_profit = net_profit + current_pos*sl_price
                elif sl_price <= initial_entry_price:
                    net_profit = net_profit - (initial_entry_price - sl_price)
                tp_counter = 0
                initial_order_size = 0.0
                risk = 0.0
                current_pos = 0.0
                sl_price = 0.0

            # If we had multiple positions - we would calculate average entry price
            if  tp_counter <= 2 and current_pos > 0 and c_current > initial_entry_price:
                if c_current >= initial_entry_price + risk and tp_counter == 0:
                    tp_counter = tp_counter + 1
                    amt_to_sell = np.floor(current_pos / 3)
                    balance = balance + amt_to_sell*c_current
                    sell.append(df.loc[index, 'date']) 
                    current_pos = current_pos - amt_to_sell
                    net_profit = net_profit + amt_to_sell*c_current 
                    profitable_trades = profitable_trades + 1

                elif c_current >= initial_entry_price + (2*risk) and tp_counter == 1:
                    tp_counter = tp_counter + 1
                    amt_to_sell = np.floor(current_pos / 3)
                    balance = balance + amt_to_sell*c_current
                    sell.append(df.loc[index, 'date']) 
                    current_pos = current_pos - amt_to_sell
                    net_profit = net_profit + amt_to_sell*c_current
                    profitable_trades = profitable_trades + 1

                elif c_current >= initial_entry_price + (3*risk) and tp_counter == 2:
                    tp_counter = tp_counter + 1
                    amt_to_sell = np.floor(current_pos / 3)
                    balance = balance + amt_to_sell*c_current
                    sell.append(df.loc[index, 'date']) 
                    current_pos = current_pos - amt_to_sell
                    net_profit = net_profit + amt_to_sell*c_current
                    profitable_trades = profitable_trades + 1

            tval = df.loc[index, 't_val']
            rej_nhypothesis = abs(tval) > crit_val

            confirmation = df.loc[index, 'drift'] > df.loc[index - 1, 'drift']

            # If we pass the ATR diversion test and drift indicates a positive expected return - reset entry until after next SL is triggered
            confirmed_entry = confirmation and rej_nhypothesis
                
   
    print(buy)
    print(sell)
    print(stop_loss)
    print(f'Profitable Trades: {profitable_trades}')Cre
    print(f'Avg Profitable Trades: {profitable_trades/(len(sell) + len(stop_loss))}')
    print(f"Trades Count: {len(buy) + len(sell) + len(stop_loss)}")
    print(f"Ending Balance: {balance}")
    print(f"Net Profit: {net_profit}")
    print(f"Unrealized Profit: {unr_profit}")
    plot_backtest(df, buy, sell, stop_loss)

def backtest_rsi(data_table, buy, sell, short_profit,  original_balance, balance, dont_buy, num_shares):
    # Loop through MACD data and generate a signal when lines cross and examine nature of cross  
    data_table = join_macd_rsi(data_table)
    for index in data_table.index: 
        if index > 1:
            if data_table.loc[index, 'RSI'] <= 30 and dont_buy == False:
                if balance - Decimal(1950) >= 0:
                    buy.append(data_table.loc[index, 'date'])
                    balance = balance - Decimal(1950)
                    amount = Decimal(1950) / Decimal(data_table.loc[index, 'close_y'])
                    num_shares = num_shares + amount
                    if len(sell) > 0:
                        short_profit = short_profit + (float(data_table.loc[(data_table.index[data_table['date'] == sell[-1]]), 'close_y']) - float(data_table.loc[index, 'close_y']))*float(100)
                    dont_buy = True  

            if  data_table.loc[index, 'RSI'] >= 70 and dont_buy == True:
                if num_shares > 0:
                    profit_to_add = num_shares * Decimal(data_table.loc[index, 'close_y'])
                    balance = balance + profit_to_add
                    num_shares = num_shares - num_shares
                    sell.append(data_table.loc[index, 'date'])
                    dont_buy = False

    print(f'Original Balance: {original_balance}')
    print(f'Current Balance: {float(balance)}')
    print(f'Profit: {float(balance - original_balance)}')
    print(f'Trades Placed: {len(buy) + len(sell)}')
    print(f'Short Profit: {short_profit}')

def join_macd_rsi(data):
    # Calculate out macd for frequency and time frame -> consider a separate function for this
    macd_data = macd.calculate_macd(data, 12, 26, 9)
    macd_data = macd_data.iloc[2:]
    rsi_series = rsi.calculate_rsi(data.loc[:, 'close'], 14, True)
    rsi_series.name = 'RSI'
    joined_table = pd.concat([macd_data, rsi_series], axis=1) # Merge
    joined_table = joined_table[:-1] # May want to drop last row
    joined_table = joined_table.round(4) # Round to whatever is needed 
    final_joined_table = pd.merge(joined_table, data, on='date') # Add dates from data table

    return final_joined_table

def trim_dates(df):
    # Trim the date and set as the index
    dates = df['date']
    dt_dates = pd.to_datetime(dates)
    trimmed_dates = dt_dates.dt.strftime('%Y-%m-%d %H:%M')
    df.loc[:, ('date')] = trimmed_dates # better practice to use .loc -> python only has to process one entity
    trimmed_df = df[['date', 'close']].copy() # Isolate close prices and dates

    return trimmed_df

# Start api log 
def start_apilog():
    api_log = logging.getLogger('API')
    api_log.setLevel(logging.DEBUG)
    api_handler = logging.FileHandler('C:\\alpaca_client\\logs\\API.log')
    api_handler.setLevel(logging.DEBUG)
    api_log.addHandler(api_handler)

    return api_log

# Start API log
api_log = start_apilog()

# Each time you request data - the current close price will change, this is why we only request data after the completion of each bar - real world
trading_client = TradingClient(ALPACA_PAPER_KEY, ALAPACA_PAPER_SECRET, paper=True)

start_time = datetime(2024, 1, 8, 0, 0, 0, tzinfo=timezone.utc)
time_frame = TimeFrame(5, TimeFrameUnit.Minute)

df = latest_data('ETH/USD', start_time, datetime.utcnow(), time_frame, api_log)

# Set vars to track over iterative executions
net_profit = 0.0 # keep track of profit (what we have actually made)
unr_profit = 0.0 # value of what we have not not sold 
sl_price = 0.0
current_pos = 0.0
crit_val = 1.96
risk = 0.0
buy = []
sell = []
stop_loss = []
confirmed_entry = False
alloc_funds = float(0.05)

df['prev_close'] = df['close'].shift(1)

 # Calculate true range
df['true_range'] = ta.true_range(df['high'], df['low'], df['close'])

# Calculate drift based on log of percent change in price
df['%Change'] = np.log(df['close'] / df['close'].shift(1))
len_drift = 14 # periods to observe drift
df['drift'] = df['%Change'].rolling(window=len_drift).mean() - (df['%Change'].rolling(window=len_drift).std() ** 2) * 0.5

# separately compute t test and average true ranges - doing it in the loop with pandas is not suggested
df['atr_f'] = average_true_range(high=df['high'], low=df['low'], close=df['close'], window=5)# average true range over last 5 bars
df['atr_s'] = average_true_range(high=df['high'], low=df['low'], close=df['close'], window=50)# average true range over last 50 bars
df['atr'] = average_true_range(df['high'], df['low'], df['close'], 14)# average true range over last 14 bars
df['sd_test'] = ta.stdev(df['true_range'], length=5)
df['t_val'] = (df['atr_f'] - df['atr_s']) / (df['sd_test'])# t test 


df['sl_pice'] = 0.0
rej_nhypothesis = False
    

#mean_reversion_test(stop_loss, risk, rej_nhypothesis, confirmed_entry,
#           net_profit, sl_price, df, current_pos, buy, sell, crit_val)
api_log = logging.getLogger('API')
api_log.setLevel(logging.DEBUG)
api_handler = logging.FileHandler('C:\\alpaca_client\\logs\\API.log')
api_handler.setLevel(logging.DEBUG)
api_log.addHandler(api_handler)
transaction_log = logging.getLogger('transaction_log')
transaction_log.setLevel(logging.INFO)
trade_file_handler = logging.FileHandler('C:\\alpaca_client\\logs\\trades.log')
trade_file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
trade_file_handler.setFormatter(trade_file_formatter)
transaction_log.addHandler(trade_file_handler)

mean_reversion_test(stop_loss, risk, rej_nhypothesis, confirmed_entry,
          net_profit, sl_price, df, current_pos, buy, sell, crit_val)