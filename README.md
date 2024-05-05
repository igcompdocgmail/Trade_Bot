This is an application that provides a bot that trades stocks and crypto with the use of a web socket connection to the Alpaca API. 
The bot can work with multiple strategies and upon each web-socket messages, the bot will run statistical analysis using OHLC data
in a given time range. The demonstrated strategy is mean reversion and is implemented with the use of pandas. 

All activity in reference to the bot will be logged in the specified log files. This includes the logging of every trade made to ensure compliance. 

I have included a file for backtesting which will help when testing new strategies in preparation for live trading - note it would need to be edited based on provided strategy.
The backtesting software is equipped to compute total money made as well as total percentage of profitable trades and will plot the bots activity over the given time period with matplot.

The bot will run until either a keyboard interrupt or the occurence of several predefined conditions. 

Example Work-flow:

```python
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
```
