import time
import asyncio
from Trader import Trader
from TradingClient import TradingClient, AsyncTradingClient
from Market import Market
from traderboard.models import SnapshotAccount, SnapshotAccountDetails, AccountTrades, AccountTransactions
from Trader import Trader
from datetime import datetime, timedelta, timezone
from django.contrib.auth.models import User


__PLATFORMS__ = ['Binance']


def take_snapshot(ta, market, now):
    '''Take snapshot of a TradingAccount'''
    assert ta.platform == market.platform, f"Trading account and market must belong to the same trading platform:\
         {ta.platform} != {market.platform}"
    tc = TradingClient.connect(ta)
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

    return snap


def update_profile(user, markets, now):
    '''Update account level user stats'''
    trader = Trader(user, markets)

    # Get pnL data wrt to 24h record
    try:
        date_from = now - timedelta(days=1)
        date_from = date_from.replace(microsecond=0, second=0, minute=0)

        stats = trader.get_stats(date_from, now, base='USDT')
        first_date = stats.iloc[0]['created_at'].to_pydatetime()
        if abs(date_from - first_date) < timedelta(hours=1):
            daily_pnl = float(stats.iloc[-1]['cum_pnl_rel'])
        else:
            daily_pnl = None
    except Exception as e:
        print(e)
        daily_pnl = None
    
    # Get pnL data wrt to 7d record
    try:
        date_from = now - timedelta(days=7)
        date_from = date_from.replace(microsecond=0, second=0, minute=0, hour=0)

        stats = trader.get_stats(date_from, now, base='USDT')
        first_date = stats.iloc[0]['created_at'].to_pydatetime()
        if abs(date_from - first_date) < timedelta(days=1):
            weekly_pnl = float(stats.iloc[-1]['cum_pnl_rel'])
        else:
            weekly_pnl = None
    except Exception as e:
        print(e)
        weekly_pnl = None

    # Get pnL data wrt to 1m record
    try:
        date_from = now - timedelta(days=30)
        date_from = date_from.replace(microsecond=0, second=0, minute=0, hour=0)

        stats = trader.get_stats(date_from, now, base='USDT')
        first_date = stats.iloc[0]['created_at'].to_pydatetime()
        if abs(date_from - first_date) < timedelta(days=1):
            monthly_pnl = float(stats.iloc[-1]['cum_pnl_rel'])
        else:
            monthly_pnl = None
    except Exception as e:
        print(e)
        monthly_pnl = None
    
    # update main ranking metrics
    user.profile.daily_pnl = daily_pnl
    user.profile.weekly_pnl = weekly_pnl
    user.profile.monthly_pnl = monthly_pnl
    user.save()

    return user


def update_order_history(ta, now, market):
    '''Update AccountTrades database with recent trades'''
    try:
        snap = AccountTrades.objects.filter(account=ta).latest('created_at')
        date_from = snap.created_at
    except AccountTrades.DoesNotExist:
        date_from = now - timedelta(days=31)
    
    tc = TradingClient.connect(ta)
    tc.set_order_history(date_from, now, market)


def update_transaction_history(ta, now, market):
    '''Update AccountTransactions database with recent funds transaction'''
    try:
        snap = AccountTransactions.objects.filter(account=ta).latest('created_at')
        date_from = snap.created_at
    except AccountTransactions.DoesNotExist:
        date_from = now - timedelta(days=31)
    
    tc = TradingClient.connect(ta)
    tc.set_order_history(date_from, now, market)


# load functions are supposed to be run once at account registration


def load_account_history(user, ta):
    '''Load past balance data at trading account registration'''
    market = Market.connect(ta.platform)
    now = datetime.now(timezone.utc)
    today = datetime.combine(now, datetime.min.time(), timezone.utc)
    date_from = now - timedelta(days=30)
    tc = TradingClient.connect(ta)
    tc.load_account_history(date_from, now, market)
    take_snapshot(ta, market, now)
    update_profile(user, None, today)
    print(f'Historic of account {ta.id} is loading...')


async def get_events(ta):
    tc = await AsyncTradingClient.connect(ta)
    try:
        await tc.get_events()
    except:
        await tc.close_connection()


async def get_trades(ta, symbol):
    tc = await AsyncTradingClient.connect(ta)
    try:
        await tc.get_trades(symbol)
    except:
        await tc.close_connection()