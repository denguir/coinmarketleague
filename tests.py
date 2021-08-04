import os
import asyncio
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


async def main(loop):
    user = await sync_to_async(User.objects.get, thread_sensitive=True)(username='vador')
    ta = await sync_to_async(TradingAccount.objects.get, thread_sensitive=True)(user=user)
    tc = await TradingClient.connect(ta)
    await tc.get_trades("BNBBTC")
    

if __name__ == "__main__":
	loop = asyncio.get_event_loop()
	loop.run_until_complete(main(loop))
	loop.close()