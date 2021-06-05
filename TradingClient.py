from multipledispatch import dispatch
import time
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta, timezone
from abc import ABC, abstractmethod
from binance.client import Client as BinanceClient
from Market import BinanceMarket, Market
from django.db.models.functions import TruncDay
from django.db.models import Max, Sum
from traderboard.models import SnapshotAccount, SnapshotAccountDetails, AccountTrades, AccountTransactions


__PLATFORMS__ = ['Binance']


class TradingClient(ABC):
    '''Abstract Trading client class to inherit from
     to integrate a trading account in a new exchange platform'''

    @staticmethod
    def trading_from(ta):
        assert(ta.platform in __PLATFORMS__)
        if ta.platform == 'Binance':
            return BinanceTradingClient(ta)

    @abstractmethod
    def __init__(self, ta):
        # ta: trading account record 
        self.ta = ta

    @abstractmethod
    def get_balances(self) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_deposit_history(self, date_from: datetime, date_to: datetime, market: Market) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_withdrawal_history(self, date_from: datetime, date_to: datetime, market: Market) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_value_table(self, balances: pd.DataFrame, market: Market, base: str) -> pd.DataFrame:
        pass


class BinanceTradingClient(TradingClient):
    '''Trading client for Binance built from a trading account 
        registered in the database'''
    # TODO:
    # include sub accounts if possible
    def __init__(self, ta):
        super().__init__(ta)
        self.client = BinanceClient(ta.api_key, ta.api_secret)
        
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
        # load stats from date_from until now
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        # get balance history
        hist = self.client.get_account_snapshot(type='SPOT', startTime=start, endTime=end)['snapshotVos']
        snapshots = pd.DataFrame([{'asset': bal['asset'], 
                                   'amount': float(bal['free']) + float(bal['locked']), 
                                   'timestamp': snap['updateTime'] + 999}
                                    for snap in hist for bal in snap['data']['balances']])

        # get transaction history
        deposits = self.get_deposit_history(date_from, date_to, market)
        withdrawals = self.get_withdrawal_history(date_from, date_to, market)

        # compute asset for which we need to track price
        assets_to_track = set(snapshots['asset']).union(set(deposits['asset'])).union(set(withdrawals['asset']))

        # get price table for each asset
        stats = pd.DataFrame()
        btc_usdt_prices = market.get_price_history('BTC', 'USDT', date_from, date_to, '1d')
        for asset in assets_to_track:
            prices = market.get_price_history(asset, 'BTC', date_from, date_to, '1d')


        # compute balance

        stats = btc_bal.merge(btc_usdt_prices, 'inner', left_on='date', right_on='close_date')
        stats['balance_usdt'] = stats['balance_btc'] * stats['close_price']
        stats['balance_usdt_open'] = stats['balance_usdt'].shift(1)
        stats['balance_btc_open'] = stats['balance_btc'].shift(1)
        stats['pnl_usdt'] = stats['balance_usdt'] - stats['balance_usdt_open']
        stats['pnl_btc'] = stats['balance_btc'] - stats['balance_btc_open']
        stats = stats[['date', 'balance_btc', 'balance_usdt', 'balance_usdt_open', 'pnl_usdt', 'pnl_btc']]
        
        # get deposit history
        deposits = self.get_deposit_history(date_from, date_to, market)
        if not deposits.empty:
            deposits['date'] = deposits['time'].apply(lambda ts: market.to_date(ts))
            for _, dep in deposits.iterrows():
                prices = market.get_daily_prices(dep['asset'], 'BTC', dep['date'], dep['date'] + timedelta(days=1))
                prices = prices.rename(columns={'close_price': 'close_price_btc'})
                prices = prices.merge(btc_usdt_prices, 'inner', on='close_date')
                prices['close_price_usdt'] = prices['close_price_btc'] * prices['close_price']
                
                prices['deposit_value_btc'] = dep['amount'] * prices['close_price_btc']
                prices['deposit_value_usdt'] = dep['amount'] * prices['close_price_usdt']
                stats = stats.merge(prices, 'left', left_on='date', right_on='close_date')
                stats = stats.fillna({'deposit_value_btc': 0.0})
                stats = stats.fillna({'deposit_value_usdt': 0.0})

                stats['pnl_btc'] = stats['pnl_btc'] - stats['deposit_value_btc']
                stats['pnl_usdt'] = stats['pnl_usdt'] - stats['deposit_value_usdt']
                stats = stats[['date', 'balance_btc', 'balance_usdt', 'pnl_btc', 'pnl_usdt']]
        
        # get withdrawal history
        withdrawals = self.get_withdrawal_history(date_from, date_to, market)
        if not withdrawals.empty:
            withdrawals['date'] = withdrawals['time'].apply(lambda ts: market.to_date(ts))
            for _, wit in withdrawals.iterrows():
                prices = market.get_daily_prices(wit['asset'], 'BTC', wit['date'], wit['date'] + timedelta(days=1))
                prices = prices.rename(columns={'close_price': 'close_price_btc'})
                prices = prices.merge(btc_usdt_prices, 'inner', on='close_date')
                prices['close_price_usdt'] = prices['close_price_btc'] * prices['close_price']

                prices['withdrawal_value_btc'] = wit['amount'] * prices['close_price_btc']
                prices['withdrawal_value_usdt'] = wit['amount'] * prices['close_price_usdt']
                stats = stats.merge(prices, 'left', left_on='date', right_on='close_date')
                stats = stats.fillna({'withdrawal_value_btc': 0.0})
                stats = stats.fillna({'withdrawal_value_usdt': 0.0})

                stats['pnl_btc'] = stats['pnl_btc'] + stats['withdrawal_value_btc']
                stats['pnl_usdt'] = stats['pnl_usdt'] + stats['withdrawal_value_usdt']
                stats = stats[['date', 'balance_btc', 'balance_usdt', 'pnl_btc', 'pnl_usdt']]

        # create snapshot account
        stats = stats.where(pd.notnull(stats), None) # replace nan by None
        for _, stat in stats.iterrows():
            snap = SnapshotAccount(account=self.ta, 
                                balance_btc=stat['balance_btc'], 
                                balance_usdt=stat['balance_usdt'], 
                                pnl_btc=stat['pnl_btc'], 
                                pnl_usdt=stat['pnl_usdt'], 
                                created_at=stat['date'].to_pydatetime(),
                                updated_at=stat['date'].to_pydatetime())
            snap.save()