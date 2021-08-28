import os
import asyncio
import aioconsole
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

from Market import Market
from TradingClient import TradingClient, AsyncTradingClient
from datetime import datetime, timedelta, timezone
from django.contrib.auth.models import User
from Trader import Trader
from traderboard.tasks import update_profile, get_events, get_trades
from traderboard.models import SnapshotAccount, SnapshotAccountDetails, TradingAccount, AccountTrades, AccountTransactions
from asgiref.sync import sync_to_async
import pandas as pd


async def main(loop):
    user = await sync_to_async(User.objects.get, thread_sensitive=True)(username='Vador')
    ta = await sync_to_async(TradingAccount.objects.get, thread_sensitive=True)(user=user)
    loop.create_task(get_trades(ta, 'BNBBTC'), name=ta.api_key)
    print(f'task {ta.api_key} created.')
    # while True:
    #     cmd = await aioconsole.ainput("New request:")
    #     if cmd.startswith('get_trades'):
    #         symbol = cmd.split()[1]
    #         loop.create_task(tc.get_trades(symbol))
    #     elif cmd.startswith('get_balances'):
    #         loop.create_task(tc.get_balances())
    # print(bal)

    
def run():
    loop = asyncio.get_event_loop()
    loop.create_task(main(loop))
    loop.run_forever()