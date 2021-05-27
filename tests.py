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

__PLATFORMS__ = ['Binance']

now = datetime.now(timezone.utc)
market = Market.trading_from('Binance')

user = User.objects.get(username='Vador')
ta = TradingAccount.objects.get(user=user)
tc = TradingClient.trading_from(ta)
snap = SnapshotAccount.objects.filter(account=ta).latest('-created_at')
date_from = snap.created_at - timedelta(days=31)
tc.set_order_history(snap.created_at - timedelta(days=31), snap, market)