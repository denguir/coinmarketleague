import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

import asyncio
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from traderboard.models import TradingAccount
from TradingClient import AsyncTradingClient
from Market import Market
from datetime import datetime, timezone
from traderboard.tasks import take_snapshot, update_profile


__PLATFORMS__ = ['Binance']


async def get_events(ta, loop):
    tc = await AsyncTradingClient.connect(ta, loop)
    await tc.get_events()
    await tc.close_connection()


if __name__ == "__main__":
    tas = TradingAccount.objects.all()
    loop = asyncio.get_event_loop()

    for ta in tas:
	    loop.create_task(get_events(ta, loop))
    
    loop.run_forever()
    loop.close()
        


