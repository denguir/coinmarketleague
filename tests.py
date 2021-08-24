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
market = Market.trading_from(ta.platform)

trader = Trader(user)

date_from = date_to - timedelta(days=31)
df = trader.get_stats(date_from, date_to)
print(df)

snaps = SnapshotAccount.objects.all().order_by('created_at')
snap_from = snaps[1]
snap_to = snaps[2]


print(snap_from.created_at)
print(snap_to.created_at)

pnl = tc.get_PnL(snap_from, snap_to, market, 'USDT')
print(pnl)