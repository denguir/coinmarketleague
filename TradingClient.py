from multipledispatch import dispatch
import time
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta, timezone
from binance import Client, AsyncClient, BinanceSocketManager
from Market import BinanceMarket, Market
from django.db.models.functions import TruncDay
from django.db.models import Max, Sum
from traderboard.models import SnapshotAccount, SnapshotAccountDetails, AccountTrades, AccountTransactions
import traderboard.celery_tasks as tasks

__PLATFORMS__ = ['Binance']


class BinanceTradingClient:
    '''Trading client for Binance built from a trading account instance'''
    # TODO:
    # include sub accounts if possible
    def __init__(self, ta):
        self.ta = ta
        self.api_key = self.ta.api_key
        self.api_secret = self.ta.api_secret

    @classmethod
    def connect(cls, ta):
        # register in db conn event
        self = cls(ta)
        self.client = Client(self.api_key, self.api_secret)
        return self

    def get_balances(self):
        # only for spot account
        info = self.client.get_account()
        balances = pd.DataFrame(info['balances'])
        balances['amount'] = balances['free'].astype(float) + balances['locked'].astype(float)
        balances = balances[balances['amount'] > 0.0]
        return balances[['asset', 'amount']]

    def get_PnL(self, snap, now, market, base='USDT'):
        deposits = self.get_deposits_value(snap.created_at, now, market, base)
        withdrawals = self.get_withdrawals_value(snap.created_at, now, market, base)
        balance_now = self.get_balances_value(market, base)

        if base == 'USDT':
            balance_from = float(snap.balance_usdt)
        elif base == 'BTC':
            balance_from = float(snap.balance_btc)

        pnl = balance_now - balance_from - deposits + withdrawals 
        return pnl

    def get_daily_balances(self, date_from, date_to, base='USDT'):
        '''Returns a historical balance time series aggregated by day'''
        snaps = SnapshotAccount.objects.filter(account=self.ta)\
                                       .annotate(day=TruncDay('created_at'))\
                                       .filter(day__range=[date_from, date_to])
        close_time = snaps.values('day')\
                          .annotate(close_time=Max('created_at'))\
                          .values('close_time')

        snaps = snaps.filter(created_at__in=close_time).order_by('day')
        snaps = snaps.values('day', 'balance_btc', 'balance_usdt')
        balance_hist = pd.DataFrame.from_records(snaps)
        if balance_hist.empty:
            balance_hist = pd.DataFrame(columns=['day', 'balance'])
        else:
            if base == 'BTC':
                balance_hist['balance'] = balance_hist['balance_btc'].astype(float)
            else:
                balance_hist['balance'] = balance_hist['balance_usdt'].astype(float)
            
            balance_hist = balance_hist[['day', 'balance']]
        return balance_hist

    def get_daily_PnL(self, date_from, date_to, base='USDT'):
        '''Return a historical PnL time series aggregated by day'''
        snaps = SnapshotAccount.objects.filter(account=self.ta)\
                                       .annotate(day=TruncDay('created_at'))\
                                       .filter(day__range=[date_from, date_to])\
                                       .values('day')\
                                       .annotate(pnl_btc=Sum('pnl_btc'))\
                                       .annotate(pnl_usdt=Sum('pnl_usdt'))\
                                       .order_by('day')

        pnl_hist = pd.DataFrame.from_records(snaps)
        if pnl_hist.empty:
            pnl_hist = pd.DataFrame(columns=['day', 'pnl'])
        else:
            if base == 'BTC':
                pnl_hist['pnl'] = pnl_hist['pnl_btc'].astype(float)
            else:
                pnl_hist['pnl'] = pnl_hist['pnl_usdt'].astype(float)

            pnl_hist = pnl_hist[['day', 'pnl']].fillna({'pnl': 0.0})
        return pnl_hist

    def get_daily_relative_PnL(self, date_from, date_to, base='USDT'):
        '''Return a historical rel PnL time series aggreagated by dat.'''
        snaps = SnapshotAccount.objects.filter(account=self.ta)\
                                       .annotate(day=TruncDay('created_at'))\
                                       .filter(day__range=[date_from, date_to])
        pnl_hist = pd.DataFrame.from_records(snaps)
        
    def get_deposit_history(self, date_from, date_to, market):
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        info = self.client.get_deposit_history(startTime=start, endTime=end, status=1)
        deposits = pd.DataFrame(columns=['time', 'asset', 'amount'])
        if info:
            deposits = pd.DataFrame(info)
            if deposits['insertTime'].dtype == np.int64:
                deposits['time'] = deposits['insertTime']
            else:
                deposits['time'] = deposits['insertTime'].apply(lambda x: market.to_timestamp(x))
            deposits['asset'] = deposits['coin']
            deposits['amount'] = deposits['amount'].astype(float)
            deposits = deposits[['time', 'asset', 'amount']]
        return deposits

    def get_withdrawal_history(self, date_from, date_to, market):
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        info = self.client.get_withdraw_history(startTime=start, endTime=end, status=6)
        withdrawals = pd.DataFrame(columns=['time', 'asset', 'amount'])
        if info:
            withdrawals = pd.DataFrame(info)
            if withdrawals['applyTime'].dtype == np.int64:
                withdrawals['time'] = withdrawals['applyTime']
            else:
                withdrawals['time'] = withdrawals['applyTime'].apply(lambda x: market.to_timestamp(x))
            withdrawals['asset'] = withdrawals['coin']
            withdrawals['amount'] = withdrawals['amount'].astype(float)
            withdrawals = withdrawals[['time', 'asset', 'amount']]
        return withdrawals

    @dispatch(datetime, datetime)
    def get_transaction_history(self, date_from, date_to):
        trans = AccountTransactions.objects.filter(account=self.ta)\
                                           .annotate(day=TruncDay('created_at'))\
                                           .filter(day__range=[date_from, date_to])\
                                           .values('created_at', 'asset', 'amount', 'side')
        trans_hist = pd.DataFrame.from_records(trans)
        if trans_hist.empty:
            trans_hist = pd.DataFrame(columns=['created_at', 'asset', 'amount', 'side'])
        else:
            trans_hist = trans_hist[['created_at', 'asset', 'amount', 'side']]
        return trans_hist

    @dispatch(datetime, datetime, BinanceMarket)
    def get_transaction_history(self, date_from, date_to, market):
        withdrawals = self.get_withdrawal_history(date_from, date_to, market)
        withdrawals['side'] = 'WITHDRAWAL'
        deposits = self.get_deposit_history(date_from, date_to, market)
        deposits['side'] = 'DEPOSIT'
        transactions = pd.concat([withdrawals, deposits])
        return transactions

    def set_transaction_history(self, date_from, date_to, market):
        transactions = self.get_transaction_history(date_from, date_to, market)
        for _, trans in transactions.iterrows():
            move = AccountTransactions(account=self.ta, 
                                        asset=trans['asset'], 
                                        amount=trans['amount'],
                                        side=trans['side'],
                                        created_at=market.to_datetime(trans['time']),
                                        updated_at=market.to_datetime(trans['time'])
                                         )
            move.save()

    @dispatch(datetime, datetime)
    def get_order_history(self, date_from, date_to):
        orders = AccountTrades.objects.filter(account=self.ta)\
                                      .annotate(day=TruncDay('created_at'))\
                                      .filter(day__range=[date_from, date_to])\
                                      .values('created_at', 'asset', 'base', 'amount', 'price', 'side')

        order_hist = pd.DataFrame.from_records(orders)
        if order_hist.empty:
            order_hist = pd.DataFrame(columns=['created_at', 'symbol', 'amount', 'price', 'side'])
        else:
            order_hist['symbol'] = order_hist['asset'] + order_hist['base']
            order_hist = order_hist[['created_at', 'symbol', 'amount', 'price', 'side']]
        return order_hist

    @dispatch(datetime, datetime, BinanceMarket)
    def get_order_history(self, date_from, date_to, market):
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        orders =  pd.DataFrame(columns=['time', 'asset', 'amount', 'base', 'price', 'side'])

        for i, exchange in market.table.iterrows():
            info = self.client.get_all_orders(symbol=exchange['symbol'], limit=1000)
            if info:
                orders_symbol = pd.DataFrame(info)
                orders_symbol = orders_symbol[orders_symbol["status"].isin(['FILLED', 'PARTIALLY_FILLED'])]
                orders_symbol = orders_symbol[orders_symbol["time"].between(start, end)]
                orders_symbol['asset'] = exchange['baseAsset']
                orders_symbol['base'] = exchange['quoteAsset']
                orders_symbol['amount'] = orders_symbol['executedQty'].astype(float)
                orders_symbol['price'] = orders_symbol['price'].astype(float)
                orders_symbol = orders_symbol[orders_symbol['amount'] > 0.0]
                orders_symbol = orders_symbol[['time', 'asset', 'amount', 'base', 'price', 'side']]
                orders = orders.append(orders_symbol, ignore_index=True)
            
            if i % 100 == 99:
                # avoid API error by marking a 1 min pause
                time.sleep(60)

        orders = orders.sort_values('time')
        return orders
    
    def set_order_history(self, date_from, date_to, market):
        orders = self.get_order_history(date_from, date_to, market)
        for _, order in orders.iterrows():
            trade = AccountTrades(account=self.ta, 
                                  asset=order['asset'], 
                                  base=order['base'], 
                                  amount=order['amount'], 
                                  price=order['price'], 
                                  side=order['side'],
                                  created_at=market.to_datetime(order['time']),
                                  updated_at=market.to_datetime(order['time'])
                                )
            trade.save()

    @dispatch(datetime, datetime, BinanceMarket)
    def get_balance_history(self, date_from, date_to, base='USDT'):
        '''Returns a historical balance time series aggregated by day'''
        snaps = SnapshotAccount.objects.filter(account=self.ta)\
                                       .annotate(day=TruncDay('created_at'))\
                                       .filter(day__range=[date_from, date_to])
        balance_hist = pd.DataFrame.from_records(snaps)
        if balance_hist.empty:
            balance_hist = pd.DataFrame(columns=['created_at', 'balance_usdt', 'pnl_usdt'])
        else:
            if base == 'BTC':
                balance_hist['balance'] = balance_hist['balance_btc'].astype(float)
            else:
                balance_hist['balance'] = balance_hist['balance_usdt'].astype(float)
            
            balance_hist = balance_hist[['day', 'balance']]
        return balance_hist

    def get_value_table(self, balances, market, base='USDT'):
        '''Compute the value of a balances using the current market prices'''
        balances['base'] = base
        balances['price'] = balances.apply(lambda x: market.get_price(x['asset'], x['base']), axis=1)
        balances['value'] = balances['amount'] * balances['price']
        return balances
    
    def get_value(self, balances, market, base='USDT'):
        '''Return the sum of balances value table'''
        if balances.empty:
            value = 0.0
        else:
            mkt = self.get_value_table(balances, market, base)
            value = sum(mkt['value'])
        return value

    def get_balances_value(self, market, base='USDT'):
        balances = self.get_balances()
        return self.get_value(balances, market, base)

    def get_deposits_value(self, date_from, date_to, market, base='USDT'):
        deposits = self.get_deposit_history(date_from, date_to, market)
        return self.get_value(deposits, market, base)

    def get_withdrawals_value(self, date_from, date_to, market, base='USDT'):
        withdrawals = self.get_withdrawal_history(date_from, date_to, market)
        return self.get_value(withdrawals, market, base)

    def get_daily_value(self, balances, market, base='USDT'):
        '''Compute the value of a balances using the historic market prices'''
        balances['day'] = balances['time'].apply(lambda ts: market.to_date(ts))
        balances['value'] = 0.0
        for _, bal in balances.iterrows():
            prices = market.get_daily_prices(bal['asset'], base, bal['day'], bal['day'] + timedelta(days=1))
            balances.loc[_, 'value'] += prices['close_price'] * bal['amount']
        return balances.groupby('day')['value'].sum().to_dict()

    def get_daily_deposits_value(self, date_from, date_to, market, base='USDT'):
        deposits = self.get_deposit_history(date_from, date_to, market)
        return self.get_daily_value(deposits, market, base)

    def get_daily_withdrawals_value(self, date_from, date_to, market, base='USDT'):
        withdrawals = self.get_withdrawal_history(date_from, date_to, market)
        return self.get_daily_value(withdrawals, market, base)

    def load_account_history(self, date_from, date_to, market):
        '''This method should be only triggered when a user registers a new 
        Binance trading account to the website'''
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)

        # get balance history
        hist = self.client.get_account_snapshot(type='SPOT', startTime=start, endTime=end)['snapshotVos']
        snapshots = pd.DataFrame([{'asset': bal['asset'], 
                                    'amount': float(bal['free']) + float(bal['locked']), 
                                    'timestamp': snap['updateTime'] + 999}
                                    for snap in hist for bal in snap['data']['balances']])

        deposits = self.get_deposit_history(date_from, date_to, market).sort_values('time')
        withdrawals = self.get_withdrawal_history(date_from, date_to, market).sort_values('time')

        assets_to_track = set(snapshots['asset']).union(set(deposits['asset'])).union(set(withdrawals['asset']))

        btc_usdt_prices = market.get_price_history('BTC', 'USDT', date_from, date_to, '1d')
        prices = pd.DataFrame(columns=['open_time', 'open_price', 'close_time', 'close_price', 'asset', 'base', 'symbol'])
        for asset in assets_to_track:
            prices = prices.append(market.get_price_history(asset, 'BTC', date_from, date_to, '1d'))

        # get prices in usdt
        prices = prices.merge(btc_usdt_prices, on=['open_time', 'close_time'], suffixes=("_btc", "_usdt"))
        prices['open_price_usdt'] = prices['open_price_btc'] * prices['open_price_usdt']
        prices['close_price_usdt'] = prices['close_price_btc'] * prices['close_price_usdt']
        prices['open_time'] = prices['open_time'].astype(int)
        prices['close_time'] = prices['close_time'].astype(int)

        # compute balances
        stats = snapshots.merge(prices, left_on=['asset', 'timestamp'], right_on=['asset_btc', 'close_time'])
        stats['open_balance_btc'] = stats['amount'] * stats['open_price_btc']
        stats['close_balance_btc'] = stats['amount'] * stats['close_price_btc']
        stats['open_balance_usdt'] = stats['amount'] * stats['open_price_usdt']
        stats['close_balance_usdt'] = stats['amount'] * stats['close_price_usdt']

        # compute pnl
        stats['pnl_btc'] = stats['close_balance_btc'] - stats['open_balance_btc']
        stats['pnl_usdt'] = stats['close_balance_usdt'] - stats['open_balance_usdt']

        # include deposits and withdrawals in pnl computation
        deposits = deposits.rename(columns={'amount': 'dep_amount', 'time': 'dep_time'})
        withdrawals = withdrawals.rename(columns={'amount': 'wit_amount', 'time': 'wit_time'})

        if not deposits.empty:
            deposits = pd.merge_asof(deposits, stats, left_on='dep_time', right_on='open_time', by='asset')
            deposits['deposits_btc'] = deposits['dep_amount'] * deposits['close_price_btc']
            deposits['deposits_usdt'] = deposits['dep_amount'] * deposits['close_price_usdt']
            deposits = deposits[['open_time', 'close_time', 'dep_time', 'dep_amount', 'asset', 'deposits_btc', 'deposits_usdt']]

            stats = stats.merge(deposits, how='left', on=['open_time', 'close_time', 'asset'])
            stats['pnl_btc'] = stats['pnl_btc'].sub(deposits['deposits_btc'], fill_value=0.0)
            stats['pnl_usdt'] = stats['pnl_usdt'].sub(deposits['deposits_usdt'], fill_value=0.0)


        if not withdrawals.empty:
            withdrawals = pd.merge_asof(withdrawals, stats, left_on='wit_time', right_on='open_time', by='asset')
            withdrawals['withdrawals_btc'] = withdrawals['wit_amount'] * withdrawals['close_price_btc']
            withdrawals['withdrawals_usdt'] = withdrawals['wit_amount'] * withdrawals['close_price_usdt']
            withdrawals = withdrawals[['open_time', 'close_time', 'wit_time', 'wit_amount', 'asset', 'withdrawals_btc', 'withdrawals_usdt']]

            stats = stats.merge(withdrawals, how='left', on=['open_time', 'close_time', 'asset'])
            stats['pnl_btc'] = stats['pnl_btc'].add(withdrawals['withdrawals_btc'], fill_value=0.0)
            stats['pnl_usdt'] = stats['pnl_usdt'].add(withdrawals['withdrawals_usdt'], fill_value=0.0)

        # group results by day
        stats = stats.groupby('open_time')

        for ts, stat in stats:
            snap = SnapshotAccount(account=self.ta, 
                                balance_btc=stat['close_balance_btc'].sum(), 
                                balance_usdt=stat['close_balance_usdt'].sum(), 
                                pnl_btc=stat['pnl_btc'].sum(),
                                pnl_usdt=stat['pnl_usdt'].sum(),
                                created_at=market.to_datetime(ts),
                                updated_at=market.to_datetime(ts))
            snap.save()

            for _, item in stat.iterrows():
                detail = SnapshotAccountDetails(snapshot=snap, asset=item['asset'], amount=item['amount'])
                detail.save()


class AsyncBinanceTradingClient:
    '''Async trading client for Binance built from a trading account instance.'''

    def __init__(self, ta):
        self.ta = ta
        self.api_key = self.ta.api_key
        self.api_secret = self.ta.api_secret

    @classmethod
    async def connect(cls, ta, loop):
        # register in db conn event
        self = cls(ta)
        self.client = await AsyncClient.create(api_key=self.api_key, api_secret=self.api_secret, loop=loop)
        self.socket_manager = BinanceSocketManager(self.client)
        return self

    async def close_connection(self):
        # register in db disconn event
        # put in celery a reconnection task
        # also some logging is needed (celery)
        await self.client.close_connection()

    async def get_events(self):
        # some logging needed here
        us = self.socket_manager.user_socket()
        async with us as uscm:
            while True:
                event = await uscm.recv()
                # put task in celery queue
                if event['e'] == "balanceUpdate":
                    tasks.record_transaction(event, self.ta)
                elif event['e'] == "executionReport" and event["X"] == "TRADE":
                    tasks.record_trade(event, self.ta)
        await self.close_connection()

    async def get_trades(self, symbol):
        ts = self.socket_manager.trade_socket(symbol)
        async with ts as tscm:
            while True:
                res = await tscm.recv()
                print(f"{res['e']} by account {self.ta.id}")
        await self.close_connection()


class TradingClient:
    def __init__(self):
        self._clients = {
            'Binance': BinanceTradingClient
        }
    
    @classmethod
    def connect(cls, ta):
        self = cls()
        client = self._clients[ta.platform]
        if not client:
            raise ValueError(f'Platform not supported - {ta.platform}')
        return client.connect(ta)


class AsyncTradingClient:
    def __init__(self):
        self._clients = {
            'Binance': AsyncBinanceTradingClient
        }
    
    @classmethod
    def connect(cls, ta, loop=None):
        self = cls()
        client = self._clients[ta.platform]
        if not client:
            raise ValueError(f'Platform not supported - {ta.platform}')
        return client.connect(ta, loop)
