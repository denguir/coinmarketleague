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
bfr = now - timedelta(days=31)
market = Market.trading_from('Binance')

df1 = market.get_price_history('GVT', 'USDT', bfr, now, '1h')
print(df1)