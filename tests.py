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
import time

__PLATFORMS__ = ['Binance']

now = datetime.now(timezone.utc)
today = datetime.combine(now, datetime.min.time(), timezone.utc)
markets = {platform : Market.trading_from(platform) for platform in __PLATFORMS__}

user = User.objects.get(username='Vador')
update_profile(user, markets, today)