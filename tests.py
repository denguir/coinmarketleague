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
    

def _get_last_snap(ta):
    snap = SnapshotAccount.objects.filter(account=ta).latest('created_at')
    return snap

async def main(loop):
    user = await sync_to_async(User.objects.get, thread_sensitive=True)(username='Vador')
    ta = await sync_to_async(TradingAccount.objects.get, thread_sensitive=True)(user=user)
    snap = await sync_to_async(_get_last_snap, thread_sensitive=True)(ta)
    tc = await TradingClient.connect(ta)
    market = await Market.connect('Binance')
    
    now = datetime.utcnow()
    pnl = await tc.get_PnL(snap, now, market, 'USDT')
    print(pnl)

    await tc.close_connection()
    await market.close_connection()



if __name__ == "__main__":
	loop = asyncio.get_event_loop()
	loop.run_until_complete(main(loop))
	loop.close()