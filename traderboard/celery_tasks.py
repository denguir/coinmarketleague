from celery import shared_task
from Market import Market
from decimal import Decimal
from asgiref.sync import sync_to_async
from .models import TradingAccount, AccountTrades, AccountTransactions

@shared_task
def add(x, y):
    return x + y
