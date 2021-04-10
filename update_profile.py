import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

from django.contrib.auth.models import User
from traderboard.models import SnapshotProfile, SnapshotProfileDetails
from TradingClient import TradingClient
from Trader import Trader
from Market import Market
from datetime import datetime, timedelta, timezone


__PLATFORMS__ = ['Binance']


if __name__ == '__main__':
    # Initialize markets
    now = datetime.now(timezone.utc)
    markets = {platform : Market.trading_from(platform) for platform in __PLATFORMS__}
    users = User.objects.all()

    for user in users:
        trader = Trader(user, markets)
        # get balances
        balance_btc = trader.get_balances_value('BTC')
        balance_usdt = trader.get_balances_value('USDT')

        # get balance details
        balance_details = trader.get_balances()

        # time ranges for PnL
        day_range = [now - timedelta(hours=30), now - timedelta(hours=24)]
        week_range = [now - timedelta(days=8), now - timedelta(days=7)]
        month_range = [now - timedelta(days=31), now - timedelta(days=30)]

        # Get pnL data wrt to last record 
        try:
            last_snap = SnapshotProfile.objects.filter(profile=user.profile).latest('created_at')
            pnl_btc = trader.get_PnL(last_snap, now, 'BTC')
            pnl_usdt = trader.get_PnL(last_snap, now, 'USDT')
        except:
            pnl_btc = None
            pnl_usdt = None

        # Get pnL data wrt to 24h record 
        try:
            daily_snap = SnapshotProfile.objects.filter(profile=user.profile)\
                                                .filter(created_at__range=day_range).latest('created_at')
            daily_pnl = trader.get_PnL(daily_snap, now, 'USDT')
        except:
            daily_pnl = None
        
        # Get pnL data wrt to 7d record
        try:
            weekly_snap = SnapshotProfile.objects.filter(profile=user.profile)\
                                            .filter(created_at__range=week_range).latest('created_at')
            weekkly_pnl = trader.get_PnL(weekly_snap, now, 'USDT')
        except:
            weekkly_pnl = None

        # Get pnL data wrt to 1m record
        try:
            monthly_snap = SnapshotProfile.objects.filter(profile=user.profile)\
                                            .filter(created_at__range=month_range).latest('created_at')
            monthly_pnl = trader.get_PnL(monthly_snap, now, 'USDT')
        except:
            monthly_pnl = None


        # update main ranking metrics
        user.profile.daily_pnl = daily_pnl
        user.profile.weekly_pnl = weekkly_pnl
        user.profile.monthly_pnl = monthly_pnl
        user.save()

        # save profile snapshot
        snap = SnapshotProfile(profile=user.profile, balance_btc=balance_btc, 
                                balance_usdt=balance_usdt, pnl_btc=pnl_btc, pnl_usdt=pnl_usdt)
        snap.save()

        # save profile details
        for asset, amount in balance_details.items():
            details = SnapshotProfileDetails(snapshot=snap, asset=asset, amount=amount)
            details.save()
        

