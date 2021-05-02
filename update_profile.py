import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

from django.contrib.auth.models import User
from traderboard.models import SnapshotProfile, SnapshotProfileDetails
from Trader import Trader
from Market import Market
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.blocking import BlockingScheduler


__PLATFORMS__ = ['Binance']
sched = BlockingScheduler()

@sched.scheduled_job('interval', minutes=30)
def update():
    # Initialize markets
    now = datetime.now(timezone.utc)
    today = datetime.combine(now, datetime.min.time(), timezone.utc)
    markets = {platform : Market.trading_from(platform) for platform in __PLATFORMS__}
    users = User.objects.all()

    for user in users:
        trader = Trader(user, markets)
        # get balances
        balance_btc = trader.get_balances_value('BTC')
        balance_usdt = trader.get_balances_value('USDT')

        # get balance details
        balance_details = trader.get_balances()

        # Get pnL data wrt to last record 
        try:
            last_snap = SnapshotProfile.objects.filter(profile=user.profile).latest('created_at')
            pnl_btc = trader.get_PnL(last_snap, now, 'BTC')
            pnl_usdt = trader.get_PnL(last_snap, now, 'USDT')
        except Exception as e:
            print(f'No PnL can be computed for user id {user.pk}.\nRoot error: {e}')
            pnl_btc = None
            pnl_usdt = None

        # save profile snapshot
        snap = SnapshotProfile(profile=user.profile, balance_btc=balance_btc, 
                                balance_usdt=balance_usdt, pnl_btc=pnl_btc, pnl_usdt=pnl_usdt)
        snap.save()

        # save profile details
        for asset, amount in balance_details.items():
            details = SnapshotProfileDetails(snapshot=snap, asset=asset, amount=amount)
            details.save()

        # Get pnL data wrt to 24h record 
        try:
            pnl_hist_usdt = trader.get_daily_cumulative_relative_PnL(today - timedelta(days=1), today, 'USDT')
            first_day_pnl = pnl_hist_usdt[today - timedelta(days=1)] # here only to make sure the time range is respected, should be 0.0
            daily_pnl = pnl_hist_usdt[today]
        except:
            daily_pnl = None
        
        # Get pnL data wrt to 7d record
        try:
            pnl_hist_usdt = trader.get_daily_cumulative_relative_PnL(today - timedelta(days=7), today, 'USDT')
            first_day_pnl = pnl_hist_usdt[today - timedelta(days=7)] # here only to make sure the time range is respected, should be 0.0
            weekly_pnl = pnl_hist_usdt[today]
        except:
            weekly_pnl = None

        # Get pnL data wrt to 1m record
        try:
            pnl_hist_usdt = trader.get_daily_cumulative_relative_PnL(today - timedelta(days=30), today, 'USDT')
            first_day_pnl = pnl_hist_usdt[today - timedelta(days=30)] # here only to make sure the time range is respected, should be 0.0
            monthly_pnl = pnl_hist_usdt[today]
        except:
            monthly_pnl = None
        
        # update main ranking metrics
        user.profile.daily_pnl = daily_pnl
        user.profile.weekly_pnl = weekly_pnl
        user.profile.monthly_pnl = monthly_pnl
        user.save()

sched.start()