from apscheduler.schedulers.blocking import BlockingScheduler
from config import ALAPACA_PAPER_SECRET, ALPACA_LIVE_KEY, ALPACA_LIVE_SECRET, ALPACA_PAPER_KEY, TIINGO_KEY
from alpaca.trading.client import TradingClient
import sys
sys.path.append('C:\\alpaca_client')
from bot import py_bot
from decimal import Decimal, ROUND_UP, getcontext # need this for precision in transactions
from datetime import datetime, timezone, utc

class functions:
    def scheduler_setup(transaction_log, api_log):
        # Establish connection to the trading client
        # Monitor for exceptions types to catch
        try:
            trading_client = TradingClient(ALPACA_PAPER_KEY, ALAPACA_PAPER_SECRET, paper=True)
        except Exception as e:
            print(f'Exception: {e}')

        # Create a new bot each time the script runs 
        trade_bot = py_bot("pyBot", trading_client, Decimal(50)) 
        dont_buy = False

        # start the scheduler
        scheduler = BlockingScheduler(timezone=utc)
        #scheduler.add_job(run_bot, 'interval', minutes=5, next_run_time=datetime.utcnow(), args=[trade_bot,transaction_log,api_log,dont_buy])


        # Handle any unexpected errors with the scheduler and shut down - also enables for user control
        # We can focus on handling particular exceptions in particular ways once we run into issues 
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            print('Shutting Down')
            scheduler.shutdown()
            exit(0)
        except Exception as e:
            print(f'Exception: {e}')
            scheduler.shutdown()