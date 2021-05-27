import time
from Trader import Trader
from TradingClient import TradingClient
from Market import Market
from traderboard.models import SnapshotAccount, SnapshotAccountDetails, TradingAccount
from Trader import Trader
from datetime import datetime, timedelta, timezone
from django.contrib.auth.models import User


__PLATFORMS__ = ['Binance']


def take_snapshot(ta, market, now):
    '''Take snapshot of a TradingAccount'''
    assert ta.platform == market.platform, f"Trading account and market must belong to the same trading platform:\
         {ta.platform} != {market.platform}"
    tc = TradingClient.trading_from(ta)
    # get balances
    balance_btc = tc.get_balances_value(market, 'BTC')
    balance_usdt = tc.get_balances_value(market, 'USDT')
    # get balance details
    balance_details = tc.get_balances()

    # Get pnL data wrt to last record 
    try:
        last_snap = SnapshotAccount.objects.filter(account=ta).latest('created_at')
        pnl_btc = tc.get_PnL(last_snap, now, market, 'BTC')
        pnl_usdt = tc.get_PnL(last_snap, now, market, 'USDT')
    except Exception as e:
        print(f'No PnL can be computed for user id {ta.user.id}.\nRoot error: {e}')
        last_snap = None
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

    if last_snap:
        # save new orders and transactions
        tc.set_order_history(last_snap.created_at, snap, market)
        tc.set_transaction_history(last_snap.created_at, snap, market)

    return snap


def update_profile(user, markets, today):
    '''Update account level user stats'''
    trader = Trader(user, markets)
    # Get pnL data wrt to 24h record 
    try:
        pnl_hist_usdt = trader.get_daily_cumulative_relative_PnL(today - timedelta(days=2), today, 'USDT')
        daily_pnl = float(pnl_hist_usdt[pnl_hist_usdt['day'] == today]['cum_pnl_perc'])
    except Exception as e:
        print(e)
        daily_pnl = None
    
    # Get pnL data wrt to 7d record
    try:
        pnl_hist_usdt = trader.get_daily_cumulative_relative_PnL(today - timedelta(days=8), today, 'USDT')
        weekly_pnl = float(pnl_hist_usdt[pnl_hist_usdt['day'] == today]['cum_pnl_perc'])
    except Exception as e:
        print(e)
        weekly_pnl = None

    # Get pnL data wrt to 1m record
    try:
        pnl_hist_usdt = trader.get_daily_cumulative_relative_PnL(today - timedelta(days=32), today, 'USDT')
        monthly_pnl = float(pnl_hist_usdt[pnl_hist_usdt['day'] == today]['cum_pnl_perc'])
    except Exception as e:
        print(e)
        monthly_pnl = None
    
    # update main ranking metrics
    user.profile.daily_pnl = daily_pnl
    user.profile.weekly_pnl = weekly_pnl
    user.profile.monthly_pnl = monthly_pnl
    user.save()

    return user


def update_all():
    now = datetime.now(timezone.utc)
    today = datetime.combine(now, datetime.min.time(), timezone.utc)
    markets = {platform : Market.trading_from(platform) for platform in __PLATFORMS__}
    users = User.objects.all()

    for user in users:
        # Collect account level data
        tas = TradingAccount.objects.filter(user=user)
        for ta in tas:
            take_snapshot(ta, markets[ta.platform], now)

        # Collect user level data
        update_profile(user, markets, today)


# load functions are supposed to be run once at account registration

def load_balance_history(ta):
    '''Load past balance data at trading account registration'''
    now = datetime.now(timezone.utc)
    market = Market.trading_from(ta.platform)
    try:
        snap = SnapshotAccount.objects.filter(account=ta).latest('-created_at')
    except SnapshotAccount.DoesNotExist:
        snap = take_snapshot(ta, market, now)
    
    date_from = snap.created_at - timedelta(days=31)
    tc = TradingClient.trading_from(ta)
    tc.set_balance_history(date_from, snap, market, '1h')


def load_order_history(ta):
    '''Load past balance data at trading account registration'''
    now = datetime.now(timezone.utc)
    market = Market.trading_from(ta.platform)
    try:
        snap = SnapshotAccount.objects.filter(account=ta).latest('-created_at')
    except SnapshotAccount.DoesNotExist:
        snap = take_snapshot(ta, market, now)
    
    date_from = snap.created_at - timedelta(days=31)
    tc = TradingClient.trading_from(ta)
    tc.set_order_history(date_from, snap, market)


def load_transaction_history(ta):
    '''Load past balance data at trading account registration'''
    now = datetime.now(timezone.utc)
    market = Market.trading_from(ta.platform)
    try:
        snap = SnapshotAccount.objects.filter(account=ta).latest('-created_at')
    except SnapshotAccount.DoesNotExist:
        snap = take_snapshot(ta, market, now)
    
    date_from = snap.created_at - timedelta(days=31)
    tc = TradingClient.trading_from(ta)
    tc.set_transaction_history(date_from, snap.created_at, market)