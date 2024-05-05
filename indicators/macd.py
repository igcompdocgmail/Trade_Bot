from tiingo import TiingoClient
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
from datetime import datetime, timedelta
import json

""" 
Lets code a strategy that uses RSI, volatility and MACD to assess risk of trade 
and runs on any time period.

Todo:
    incorporate the RSI
    Find a way to assess risk and calculate the strength of the trade - money spend could be based on strength
    Consider average distance of signal and macd during height of price swing - why not also consider volatility here 
 """

# Calculate and return a df that represents an MACD indicator
def calculate_macd(data, short_window, long_window, signal_window):
    

    # Calculate MACD and signal using separate series, then return their concatenation
    dates = pd.Series(data['date'], name= 'date')
    closes = pd.Series(data['close'], name= 'close')
    short_ema = pd.Series(data['close'].ewm(span=short_window, adjust=False).mean())
    long_ema = pd.Series(data['close'].ewm(span=long_window, adjust=False).mean())
    macd = pd.Series(short_ema-long_ema, name='MACD')
    signal = pd.Series(macd.ewm(ignore_na=False, span=signal_window, adjust=False).mean(), name='Signal_Line')
    histogram = pd.Series(macd-signal, name='Histogram')
    
    return pd.concat([dates, macd, signal, histogram, closes], axis=1)

def plot_macd(macd_df):
    # Set the plot size w x h
    plt.figure(figsize=(14,6))

    # Set x and y axis - give the line a color and the axis a lavel
    plt.plot(macd_df.index, macd_df['MACD'], label='MACD', color='blue')
    plt.plot(macd_df.index, macd_df['Signal_Line'], label='Signal Line', color='orange')

    # creates horizontal line across the plot - dashed and gray
    plt.axhline(y=0, color='gray', linestyle='--', linewidth=1)

    # Adding labels and title
    plt.title('MACD and Signal Line')
    plt.xlabel('Date')
    plt.ylabel('MACD Value')

    # Set intervals
    locator = MaxNLocator(nbins=5)
    plt.gca().xaxis.set_major_locator(locator)

    # Add legend
    plt.legend()

    plt.show()

