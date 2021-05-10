import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

from Market import Market
from TradingClient import TradingClient
from datetime import datetime, timedelta, timezone
from django.contrib.auth.models import User
from traderboard.models import SnapshotAccount, SnapshotAccountDetails, TradingAccount

# Create your tests here.
date_from = datetime.utcnow() - timedelta(days=31)
user = User.objects.get(username='Vador')
ta = TradingAccount.objects.get(user=user)

# market = Market.trading_from(ta.platform)
# tc = TradingClient.trading_from(ta)
# tc.load_past_stats(date_from, market)

snaps = SnapshotAccount.objects.filter(account=ta)
for snap in snaps:
    print(snap.__dict__)