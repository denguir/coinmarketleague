import time
import asyncio
from django.contrib.auth.models import User
from traderboard.models import TradingAccount
from Market import Market
from datetime import datetime, timezone
from traderboard.tasks import get_events, get_trades
from asgiref.sync import sync_to_async
from contextlib import suppress


__PLATFORMS__ = ['Binance']


@sync_to_async(thread_sensitive=True)
def get_trading_accounts():
    tas_qs = TradingAccount.objects.all()
    tas = {}
    for ta in tas_qs:
        tas[ta.api_key] = ta
    return tas


async def update_tasks(loop):
    while True:
        tas = await get_trading_accounts()
        tasks = {task.get_name(): task for task in asyncio.all_tasks(loop=loop)}
        tasks_to_create = set(tas.keys()) - set(tasks.keys())

        for task_id in tasks_to_create:
            ta = tas[task_id]
            loop.create_task(get_events(ta), name=task_id)
            print(f'task {task_id} successfully created.')
        
        await asyncio.sleep(10)


def run():
    loop = asyncio.get_event_loop()
    loop.create_task(update_tasks(loop), name='main')
    loop.run_forever()


