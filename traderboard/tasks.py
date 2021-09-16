import time
from celery import shared_task
from Trader import Trader
from TradingClient import TradingClient
from Market import Market
from Trader import Trader
from datetime import datetime, timedelta, timezone
from django.contrib.auth.models import User
from django.db import IntegrityError
from decimal import Decimal
from traderboard.models import (TradingAccount, 
                                SnapshotAccount, 
                                SnapshotAccountDetails, 
                                AccountTrades, 
                                AccountTransactions)


__PLATFORMS__ = ['Binance']


def take_snapshot(ta, market, now):
    '''Take snapshot of a TradingAccount'''
    assert ta.platform == market.platform, f"Trading account and market\
        must belong to the same trading platform: {ta.platform} != {market.platform}"
    tc = TradingClient.connect(ta)
    # get balances
    balance_btc = Decimal(tc.get_balances_value(market, 'BTC'))
    balance_usdt = Decimal(tc.get_balances_value(market, 'USDT'))
    # get balance details
    balance_details = tc.get_balances()

    # Get pnL data wrt to last record 
    try:
        last_snap = SnapshotAccount.objects.filter(account=ta).latest('created_at')
        pnl_btc = Decimal(tc.get_pnl(last_snap, now, market, 'BTC'))
        pnl_usdt = Decimal(tc.get_pnl(last_snap, now, market, 'USDT'))
    except Exception as e:
        print(f'No PnL can be computed for account {ta.id}.\nRoot error: {e}')
        last_snap = None
        pnl_btc = None
        pnl_usdt = None

    # save account snapshot
    snap = SnapshotAccount(account=ta, 
                           balance_btc=balance_btc, 
                           balance_usdt=balance_usdt, 
                           pnl_btc=pnl_btc, 
                           pnl_usdt=pnl_usdt, 
                           created_at=now, 
                           updated_at=now)

    try:
        snap.save()
        # save account details
        for record in balance_details.itertuples():
            details = SnapshotAccountDetails(snapshot=snap, 
                                            asset=record.asset, 
                                            amount=Decimal(record.amount)
                                            )
            try:
                details.save()
            except IntegrityError as e:
                print('Snapshot detail duplicate detected, record operation dismissed.')

    except IntegrityError as e:
        print('Snapshot duplicate detected, record operation dismissed.')

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
            daily_pnl = Decimal(stats.iloc[-1]['cum_pnl_rel'])
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
            weekly_pnl = Decimal(stats.iloc[-1]['cum_pnl_rel'])
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
        if abs(date_from - first_date) < timedelta(days=2):
            monthly_pnl = Decimal(stats.iloc[-1]['cum_pnl_rel'])
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


def record_transaction(event, ta_id):
    ta = TradingAccount.objects.get(id=ta_id)
    if ta:
        asset = event['a']
        amount = Decimal(event['d'])
        side = 'DEPOSIT' if amount >= 0 else 'WITHDRAWAL'
        date = Market.to_datetime(event['E'])
        trans = AccountTransactions(account=ta,
                                    created_at=date,
                                    updated_at=date,
                                    asset=asset,
                                    amount=abs(amount),
                                    side=side
                                    )
        try:
            trans.save()
            print(f'Transaction of account {ta_id} recorded.')
        except IntegrityError as e:
            print('Transaction duplicate detected, record operation dismissed.')

    else:
        raise Exception(f'Trading account {ta_id} does not exist.')


def record_trade(event, ta_id):
    ta = TradingAccount.objects.get(id=ta_id)
    if ta:
        date = Market.to_datetime(event['E'])
        symbol = event['s']
        side = event['S']
        quantity = Decimal(event['l'])
        price = Decimal(event['L'])
        # get average order price if price not available
        if price == 0:
            try:
                price = Decimal(event['Z']) / Decimal(event['z'])
            except ZeroDivisionError:
                price = Decimal(0)

        trade = AccountTrades(account=ta,
                            created_at=date,
                            updated_at=date,
                            symbol=symbol,
                            amount=quantity,
                            price=price,
                            side=side,
                            )
        try:
            trade.save()
            print(f'Trade of account {ta_id} recorded.')
        except IntegrityError as e:
            print('Trade duplicate detected, record operation dismissed.')

    else:
        raise Exception(f'Trading account {ta_id} does not exist.')
    

# functions that are supposed to be run once at account registration

def load_account_history(user_id, ta_id):
    '''Load past balance data at trading account registration'''
    user = User.objects.get(id=user_id)
    ta = TradingAccount.objects.get(id=ta_id)
    market = Market.connect(ta.platform)
    tc = TradingClient.connect(ta)
    now = datetime.now(timezone.utc)

    for _ in range(1):
        try:
            first_snap = SnapshotAccount.objects.filter(account=ta).earliest('created_at')
            date_to = first_snap.created_at
        except:
            date_to = now
            
        date_from = date_to - timedelta(days=30)
        tc.load_transaction_history(date_from, date_to)
        print(f'Transaction history of accout {ta.id} loaded successfully.')
        tc.load_snapshot_history(date_from, date_to, market)
        print(f'Snapshot history of account {ta.id} loaded succesfully.')
    
    take_snapshot(ta, market, now)
    update_profile(user, None, now)
    