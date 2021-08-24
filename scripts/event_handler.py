import time
import asyncio
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from traderboard.models import TradingAccount
from TradingClient import AsyncTradingClient
from Market import Market
from datetime import datetime, timezone
from traderboard.tasks import get_events
from asgiref.sync import sync_to_async

__PLATFORMS__ = ['Binance']


def update_tasks(loop):
    while True:
        tas = {ta.api_key: ta for ta in TradingAccount.objects.all()}
        tasks = {task.get_name(): task for task in asyncio.all_tasks(loop=loop)}

        tasks_to_cancel = set(tasks.keys()) - set(tas.keys())
        tasks_to_create = set(tas.keys()) - set(tasks.keys())

        for task_id in tasks_to_cancel:
            task = tasks[task_id]
            task.cancel()

            if task.cancelled() or task.done():
                print(f'task {task_id} successfully canceled.')
            else:
                print(f'task {task_id} failed to cancel.')

        
        for task_id in tasks_to_create:
            loop.create_task(get_events(tas[task_id]), name=task_id)
            print(f'task {task_id} successfully created.')
        
        time.sleep(10)
        

def run():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(update_tasks(loop))
    loop.close()


