import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

from Market import Market
from TradingClient import TradingClient
from datetime import datetime, timedelta, timezone
from django.contrib.auth.models import User
from Trader import Trader
from traderboard.models import SnapshotAccount, SnapshotAccountDetails, TradingAccount

__PLATFORMS__ = ['Binance']

now = datetime.now(timezone.utc)
today = datetime.combine(now, datetime.min.time(), timezone.utc)
markets = {platform : Market.trading_from(platform) for platform in __PLATFORMS__}
user = User.objects.get(username='Vador')

ta = TradingAccount.objects.get(user=user)
tc = TradingClient.trading_from(ta)

market = markets[ta.platform]
last_snap = SnapshotAccount.objects.filter(account=ta).latest('created_at')
date_from = now - timedelta(days=31)
orders = tc.get_order_history(date_from, last_snap, market)
print(orders)