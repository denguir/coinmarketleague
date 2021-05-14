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

balance_btc = tc.get_balances_value(markets[ta.platform], 'BTC')
print(balance_btc)

balance_details = tc.get_balances()
print(balance_details)


print(tc.get_daily_PnL(today - timedelta(days=31), today, 'USDT'))
# last_snap = SnapshotAccount.objects.filter(account=ta).latest('created_at')
# print(last_snap.__dict__)
# pnl_btc = tc.get_PnL(last_snap, now, markets[ta.platform], 'BTC')
# print(pnl_btc)

# trader = Trader(user, markets)
# pnl_hist_usdt = trader.get_daily_cumulative_relative_PnL(today - timedelta(days=31), today, 'USDT')
# print(pnl_hist_usdt)
# print(pnl_hist_usdt[pnl_hist_usdt['day'] == today]['cum_pnl_perc'])