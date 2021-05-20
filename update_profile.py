import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

from django.contrib.auth.models import User
from traderboard.models import SnapshotAccount, SnapshotAccountDetails, TradingAccount
from Trader import Trader
from Market import Market
from TradingClient import TradingClient
from datetime import datetime, timedelta, timezone


__PLATFORMS__ = ['Binance']


if __name__ == '__main__':
    # Take time snapshot of market state
    now = datetime.now(timezone.utc)
    today = datetime.combine(now, datetime.min.time(), timezone.utc)
    markets = {platform : Market.trading_from(platform) for platform in __PLATFORMS__}
    users = User.objects.all()


    for user in users:
        # Collect account level data
        tas = TradingAccount.objects.filter(user=user)
        for ta in tas:
            tc = TradingClient.trading_from(ta)
            # get balances
            balance_btc = tc.get_balances_value(markets[ta.platform], 'BTC')
            balance_usdt = tc.get_balances_value(markets[ta.platform], 'USDT')

            # get balance details
            balance_details = tc.get_balances()

            # Get pnL data wrt to last record 
            try:
                last_snap = SnapshotAccount.objects.filter(account=ta).latest('created_at')
                pnl_btc = tc.get_PnL(last_snap, now, markets[ta.platform], 'BTC')
                pnl_usdt = tc.get_PnL(last_snap, now, markets[ta.platform], 'USDT')
            except Exception as e:
                print(f'No PnL can be computed for user id {user.pk}.\nRoot error: {e}')
                pnl_btc = None
                pnl_usdt = None

            # save account snapshot
            snap = SnapshotAccount(account=ta, balance_btc=balance_btc, balance_usdt=balance_usdt, 
                                   pnl_btc=pnl_btc, pnl_usdt=pnl_usdt, created_at=now, updated_at=now)
            snap.save()

            # save account details
            for record in balance_details.itertuples():
                details = SnapshotAccountDetails(snapshot=snap, asset=record.asset, amount=record.amount)
                details.save()

        # Collect user level data
        trader = Trader(user, markets)
        # Get pnL data wrt to 24h record 
        try:
            pnl_hist_usdt = trader.get_daily_cumulative_relative_PnL(now - timedelta(days=2), now, 'USDT')
            print(pnl_hist_usdt)
            daily_pnl = float(pnl_hist_usdt[pnl_hist_usdt['day'] == today]['cum_pnl_perc'])
            print(daily_pnl)
        except Exception as e:
            print(e)
            daily_pnl = None
        
        # Get pnL data wrt to 7d record
        try:
            pnl_hist_usdt = trader.get_daily_cumulative_relative_PnL(now - timedelta(days=8), now, 'USDT')
            print(pnl_hist_usdt)
            weekly_pnl = float(pnl_hist_usdt[pnl_hist_usdt['day'] == today]['cum_pnl_perc'])
            print(weekly_pnl)
        except Exception as e:
            print(e)
            weekly_pnl = None

        # Get pnL data wrt to 1m record
        try:
            pnl_hist_usdt = trader.get_daily_cumulative_relative_PnL(now - timedelta(days=32), now, 'USDT')
            print(pnl_hist_usdt)
            monthly_pnl = float(pnl_hist_usdt[pnl_hist_usdt['day'] == today]['cum_pnl_perc'])
            print(monthly_pnl)
        except Exception as e:
            print(e)
            monthly_pnl = None
        
        # update main ranking metrics
        user.profile.daily_pnl = daily_pnl
        user.profile.weekly_pnl = weekly_pnl
        user.profile.monthly_pnl = monthly_pnl
        user.save()