import os
import asyncio
import aioconsole
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

from Market import Market
from TradingClient import TradingClient
from datetime import datetime, timedelta, timezone
from django.contrib.auth.models import User
from Trader import Trader
from traderboard.tasks import update_profile
from traderboard.models import SnapshotAccount, SnapshotAccountDetails, TradingAccount, AccountTrades, AccountTransactions
import pandas as pd
from asgiref.sync import sync_to_async


# async def main(loop):
#     user = await sync_to_async(User.objects.get, thread_sensitive=True)(username='Vador')
#     ta = await sync_to_async(TradingAccount.objects.get, thread_sensitive=True)(user=user)
#     tc = await TradingClient.connect(ta)
#     while True:
#         cmd = await aioconsole.ainput("New request:")
#         if cmd.startswith('get_trades'):
#             symbol = cmd.split()[1]
#             loop.create_task(tc.get_trades(symbol))
#         elif cmd.startswith('get_balances'):
#             loop.create_task(tc.get_balances())
#     print(bal)
    

async def main(loop):
    bm = await Market.connect('Binance')
    price = await bm.get_price('CTSI', 'ETH')
    print(price)



if __name__ == "__main__":
	loop = asyncio.get_event_loop()
	loop.run_until_complete(main(loop))
	loop.close()