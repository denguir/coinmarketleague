import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

from Market import Market
from TradingClient import TradingClient
from datetime import datetime, timedelta, timezone
from django.contrib.auth.models import User
from Trader import Trader
from traderboard.models import SnapshotAccount, SnapshotAccountDetails, TradingAccount, AccountTrades, AccountTransactions
import time

__PLATFORMS__ = ['Binance']

now = datetime.now(timezone.utc)
market = Market.trading_from('Binance')

user = User.objects.get(username='Vador')
ta = TradingAccount.objects.get(user=user)
tc = TradingClient.trading_from(ta)
# snap = SnapshotAccount.objects.filter(account=ta).latest('-created_at')
# date_from = snap.created_at - timedelta(days=31)
# orders = tc.get_order_history(date_from, snap, market)
# print(orders)

print(market.table.head())
print(len(market.table))