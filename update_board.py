import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

from django.contrib.auth.models import User
from traderboard.models import TradingAccount, SnapshotAccount, SnapshotAccountDetails
from TradingClient import TradingClient
from Market import Market
from datetime import datetime, timedelta
from django.db.models import Sum, Max


__PLATFORMS__ = ['Binance']


if __name__ == '__main__':
    # Initialize markets 
    markets = {platform : Market.trading_from(platform) for platform in __PLATFORMS__}

    tas = TradingAccount.objects.all()
    # Update trading account's balance
    for ta in tas:
        tc = TradingClient.trading_from(ta)
        balance_details = tc.get_balances()
        balance_btc = tc.get_balances_value(markets[ta.platform], 'BTC')
        balance_usdt = tc.get_balances_value(markets[ta.platform], 'USDT')

        # save snapshot and details
        snap = SnapshotAccount(account=ta, balance_btc=balance_btc, balance_usdt=balance_usdt)
        snap.save()
        for asset, amount in balance_details.items():
            details = SnapshotAccountDetails(snapshot=snap, asset=asset, amount=amount)
            details.save()

    # Update user's profile
    users = User.objects.all()
    for user in users:
        tas = TradingAccount.objects.filter(user=user)
        balance_now = 0.0
        balance_1d = 0.0
        balance_1w = 0.0
        balance_1m = 0.0

        deposits_1d = 0.0
        deposits_1w = 0.0
        deposits_1m = 0.0

        withdrawals_1d = 0.0
        withdrawals_1w = 0.0
        withdrawals_1m = 0.0

        for ta in tas.iterator():
            tc = TradingClient.trading_from(ta)
            last_snap = SnapshotAccount.objects.filter(account=ta).latest('created_at')

            day_range = [last_snap.created_at - timedelta(hours=30), last_snap.created_at - timedelta(hours=24)]
            week_range = [last_snap.created_at - timedelta(days=8), last_snap.created_at - timedelta(days=7)]
            month_range = [last_snap.created_at - timedelta(days=31), last_snap.created_at - timedelta(days=30)]

            balance_now += float(last_snap.balance_usdt)
            try:
                daily_snap = SnapshotAccount.objects.filter(account=ta)\
                                            .filter(created_at__range=day_range).latest('created_at')
                balance_1d += float(daily_snap.balance_usdt)
                deposits_1d += tc.get_deposits_value(daily_snap.created_at, last_snap.created_at, markets[ta.platform], 'USDT')
                withdrawals_1d += tc.get_withdrawals_value(daily_snap.created_at, last_snap.created_at, markets[ta.platform], 'USDT')
            except:
                pass

            try:
                weekly_snap = SnapshotAccount.objects.filter(account=ta)\
                                             .filter(created_at__range=week_range).latest('created_at')
                balance_1w += float(weekly_snap.balance_usdt)
                deposits_1w += tc.get_deposits_value(weekly_snap.created_at, last_snap.created_at, markets[ta.platform], 'USDT')
                withdrawals_1w += tc.get_withdrawals_value(weekly_snap.created_at, last_snap.created_at, markets[ta.platform], 'USDT')
            except:
                pass

            try:
                monthly_snap = SnapshotAccount.objects.filter(account=ta)\
                                              .filter(created_at__range=month_range).latest('created_at')
                balance_1m += float(monthly_snap.balance_usdt)
                deposits_1m += tc.get_deposits_value(monthly_snap.created_at, last_snap.created_at, markets[ta.platform], 'USDT')
                withdrawals_1m += tc.get_withdrawals_value(monthly_snap.created_at, last_snap.created_at, markets[ta.platform], 'USDT')
            except:
                pass

        if balance_1d > 0:
            pnl_1d = (balance_now - deposits_1d + withdrawals_1d - balance_1d) / balance_1d
        else:
            pnl_1d = None
        
        if balance_1w > 0:
            pnl_1w = (balance_now - deposits_1w + withdrawals_1w - balance_1w) / balance_1w
        else:
            pnl_1w = None

        if balance_1m > 0:
            pnl_1m = (balance_now - deposits_1m + withdrawals_1m - balance_1m) / balance_1m
        else:
            pnl_1m = None

        user.profile.daily_pnl = pnl_1d
        user.profile.weekly_pnl = pnl_1w
        user.profile.monthly_pnl = pnl_1m
        user.save()