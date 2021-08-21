import os
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
from django.db.models.functions import Trunc, TruncDay
import pandas as pd


__PLATFORMS__ = ['Binance']


date_to = datetime.now(timezone.utc)
user = User.objects.get(username='Vador')
ta = TradingAccount.objects.get(user=user)
tc = TradingClient.trading_from(ta)

trader = Trader(user)

date_from = date_to - timedelta(days=30)
df = trader.get_stats(date_from, date_to)
print(df)

df = trader.get_aggregated_stats(date_from, date_to, freq='D')
print(df)