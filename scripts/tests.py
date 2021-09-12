from unicorn_binance_websocket_api.unicorn_binance_websocket_api_manager import BinanceWebSocketApiManager
from traderboard.models import TradingAccount
from Market import Market
from TradingClient import TradingClient
from datetime import datetime, timedelta, timezone
from traderboard.tasks import record_trade, record_transaction
import logging
import time
import threading
import json
import os


def run():
    ta = TradingAccount.objects.all()[0]
    market = Market.connect(ta.platform)
    tc = TradingClient.connect(ta)
    
    date_from = datetime(2021, 9, 1).replace(tzinfo=timezone.utc)
    date_to = date_from + timedelta(days=30)
    tc.load_snapshot_history(date_from, date_to, market)



