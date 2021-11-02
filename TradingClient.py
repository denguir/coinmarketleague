from multipledispatch import dispatch
import time
import pandas as pd
import numpy as np
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from binance import Client
from Market import BinanceMarket, Market
from django.db.models import Max, Sum, Min
from django.db.models.functions import Trunc
from django.db import IntegrityError
from traderboard.models import (SnapshotAccount, 
                                SnapshotAccountDetails, 
                                AccountTrades, 
                                AccountTransactions)


__PLATFORMS__ = ['Binance']


class BaseTradingClient:
    '''Provide with all the methods exclusively querying the local database.
       A TradingClient should extend this class to get access to localy stored data.'''

    def __init__(self, ta):
        self.ta = ta
    
    def get_snapshot_history(self, date_from, date_to, base='USDT'):
        snaps = SnapshotAccount.objects.filter(account=self.ta)\
                                       .filter(created_at__range=[date_from, date_to])\
                                       .values('created_at', 
                                               'pnl_usdt', 
                                               'pnl_btc', 
                                               'balance_usdt', 
                                               'balance_btc')
        snaps = pd.DataFrame.from_records(snaps)
        if snaps.empty:
            snaps = pd.DataFrame(columns=['created_at', 'pnl', 'balance'])
        else:
            if base == 'BTC':
                snaps['pnl'] = snaps['pnl_btc'].astype(float)
                snaps['balance'] = snaps['balance_btc'].astype(float)
            else:
                snaps['pnl'] = snaps['pnl_usdt'].astype(float)
                snaps['balance'] = snaps['balance_usdt'].astype(float)

            snaps = snaps[['created_at', 'pnl', 'balance']]
        return snaps

    def get_transaction_history(self, date_from, date_to):
        trans = AccountTransactions.objects.filter(account=self.ta)\
                                           .filter(created_at__range=[date_from, date_to])\
                                           .values('created_at', 
                                                   'asset', 
                                                   'amount', 
                                                   'side')
        trans_hist = pd.DataFrame.from_records(trans)
        if trans_hist.empty:
            trans_hist = pd.DataFrame(columns=['created_at', 'asset', 'amount', 'side'])
        else:
            trans_hist = trans_hist[['created_at', 'asset', 'amount', 'side']]
        return trans_hist

    def get_deposit_history(self, date_from, date_to):
        trans_hist = self.get_transaction_history(date_from, date_to)
        dep_hist = trans_hist[trans_hist['side'] == 'DEPOSIT']
        dep_hist['amount'] = dep_hist['amount'].astype(float)
        return dep_hist

    def get_withdrawal_history(self, date_from, date_to):
        trans_hist = self.get_transaction_history(date_from, date_to)
        wit_hist = trans_hist[trans_hist['side'] == 'WITHDRAWAL']
        wit_hist['amount'] = wit_hist['amount'].astype(float)
        return wit_hist

    def get_trade_history(self, date_from, date_to):
        trades = AccountTrades.objects.filter(account=self.ta)\
                                      .filter(created_at__range=[date_from, date_to])\
                                      .values('created_at', 
                                              'symbol',
                                              'amount',
                                              'price',
                                              'side')
        trade_hist = pd.DataFrame.from_records(trades)
        if trade_hist.empty:
            trade_hist = pd.DataFrame(columns=['created_at', 'symbol', 'amount', 'price', 'side'])
        else:
            trade_hist = trade_hist[['created_at', 'symbol', 'amount', 'price', 'side']]
        return trade_hist


class BinanceTradingClient(BaseTradingClient):
    '''Client for Binance trading account.'''

    def __init__(self, ta):
        super(BinanceTradingClient, self).__init__(ta)
        self.api_key = self.ta.api_key
        self.api_secret = self.ta.api_secret
    
    @classmethod
    def connect(cls, ta):
        self = cls(ta)
        self.client = Client(self.api_key, self.api_secret)
        return self

    def get_balances(self):
        '''Get current balances of SPOT account.'''
        info = self.client.get_account()
        balances = pd.DataFrame(info['balances'])
        balances['amount'] = balances['free'].astype(float) + balances['locked'].astype(float)
        balances = balances[balances['amount'] > 0.0]
        return balances[['asset', 'amount']]

    def get_value_table(self, balances, market, base='USDT'):
        '''Compute the value of a balances using the current market prices.'''
        balances['base'] = base
        balances['price'] = balances.apply(lambda x: market.get_price(x['asset'], x['base'])['lastPrice'], axis=1)
        balances['value'] = balances['amount'] * balances['price']
        return balances

    def get_value(self, balances, market, base='USDT'):
        '''Return the total value of <balances> in <base> units'''
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
        '''To be used only when date_from and date_to are close'''
        deposits = self.get_deposit_history(date_from, date_to)
        return self.get_value(deposits, market, base)

    def get_withdrawals_value(self, date_from, date_to, market, base='USDT'):
        '''To be used only when date_from and date_to are close'''
        withdrawals = self.get_withdrawal_history(date_from, date_to)
        return self.get_value(withdrawals, market, base)

    def get_pnl(self, snap, now, market, base='USDT'):
        '''Compute PnL since snap until now. Only valid for small time intervals.'''
        deposits = self.get_deposits_value(snap.created_at, now, market, base)
        withdrawals = self.get_withdrawals_value(snap.created_at, now, market, base)
        balance_now = self.get_balances_value(market, base)

        if base == 'USDT':
            balance_from = float(snap.balance_usdt)
        elif base == 'BTC':
            balance_from = float(snap.balance_btc)

        pnl = balance_now - balance_from - deposits + withdrawals 
        return pnl

    def get_api_deposit_history(self, date_from, date_to):
        '''Retrieve deposits from REST API between date_from and date_to.'''
        start = Market.to_timestamp(date_from)
        end = Market.to_timestamp(date_to)

        # get crypto deposits
        crypto_info = self.client.get_deposit_history(startTime=start, 
                                                      endTime=end, 
                                                      status=1)

        crypto_deposits = pd.DataFrame(columns=['created_at', 'time', 'asset', 'amount', 'side'])                                                 
        if crypto_info:
            crypto_deposits = pd.DataFrame(crypto_info)
            crypto_deposits['time'] = crypto_deposits['insertTime'].astype(int)
            crypto_deposits['created_at'] = crypto_deposits['time'].apply(lambda x: Market.to_datetime(x))
            crypto_deposits['amount'] = crypto_deposits['amount'].astype(float)
            crypto_deposits['asset'] = crypto_deposits['coin']
            crypto_deposits['side'] = 'DEPOSIT'
            crypto_deposits = crypto_deposits[['created_at', 'time', 'asset', 'amount', 'side']]
        
        # get fiat deposits
        fiat_info = self.client.get_fiat_deposit_withdraw_history(transactionType=0,
                                                                  beginTime=start,
                                                                  endTime=end)['data']

        fiat_deposits = pd.DataFrame(columns=['created_at', 'time', 'asset', 'amount', 'side'])    
        if fiat_info:
            fiat_deposits = pd.DataFrame(fiat_info)
            fiat_deposits = fiat_deposits[fiat_deposits['status'] == 'Successful']
            fiat_deposits['time'] = fiat_deposits['createTime']
            fiat_deposits['created_at'] = fiat_deposits['time'].apply(lambda x: Market.to_datetime(x))
            fiat_deposits['amount'] = fiat_deposits['amount'].astype(float)
            fiat_deposits['asset'] = fiat_deposits['fiatCurrency']
            fiat_deposits['side'] = 'DEPOSIT'
            fiat_deposits = fiat_deposits[['created_at', 'time', 'asset', 'amount', 'side']]
        
        deposits = pd.concat([crypto_deposits, fiat_deposits]).sort_values('time')
        return deposits

    def get_api_withdrawal_history(self, date_from, date_to):
        '''Retrieve withdrawals from REST API between date_from and date_to.'''
        start = Market.to_timestamp(date_from)
        end = Market.to_timestamp(date_to)
        
        # get crypto withdrawals
        crypto_info = self.client.get_withdraw_history(startTime=start, 
                                                       endTime=end, 
                                                       status=6)

        crypto_withdrawals = pd.DataFrame(columns=['created_at', 'time', 'asset', 'amount', 'side'])
        if crypto_info:
            crypto_withdrawals = pd.DataFrame(crypto_info)
            crypto_withdrawals['time'] = crypto_withdrawals['applyTime'].apply(lambda x: Market.to_timestamp(x))
            crypto_withdrawals['created_at'] = crypto_withdrawals['time'].apply(lambda x: Market.to_datetime(x))
            crypto_withdrawals['amount'] = crypto_withdrawals['amount'].astype(float)
            crypto_withdrawals['asset'] = crypto_withdrawals['coin']
            crypto_withdrawals['side'] = 'WITHDRAWAL'
            crypto_withdrawals = crypto_withdrawals[['created_at', 'time', 'asset', 'amount', 'side']]

        # get fiat withdrawals
        fiat_info = self.client.get_fiat_deposit_withdraw_history(transactionType=1,
                                                                  beginTime=start,
                                                                  endTime=end)['data']

        fiat_withdrawals = pd.DataFrame(columns=['created_at', 'time', 'asset', 'amount', 'side'])
        if fiat_info:
            fiat_withdrawals = pd.DataFrame(fiat_info)
            fiat_withdrawals = fiat_withdrawals[fiat_withdrawals['status'] == 'Successful']
            fiat_withdrawals['time'] = fiat_withdrawals['createTime']
            fiat_withdrawals['created_at'] = fiat_withdrawals['time'].apply(lambda x: Market.to_datetime(x))
            fiat_withdrawals['amount'] = fiat_withdrawals['amount'].astype(float)
            fiat_withdrawals['asset'] = fiat_withdrawals['fiatCurrency']
            fiat_withdrawals['side'] = 'WITHDRAWAL'
            fiat_withdrawals = fiat_withdrawals[['created_at', 'time', 'asset', 'amount', 'side']]

        withdrawals = pd.concat([crypto_withdrawals, fiat_withdrawals]).sort_values('time')
        return withdrawals

    def get_api_transaction_history(self, date_from, date_to):
        '''Retrieve transactions from REST API between date_from and date_to.'''
        deposits = self.get_api_deposit_history(date_from, date_to)
        withdrawals = self.get_api_withdrawal_history(date_from, date_to)
        trans_hist = pd.concat([deposits, withdrawals])
        return trans_hist

    def load_transaction_history(self, date_from, date_to):
        '''Load transactions between date_from and date_to in local database.'''
        trans_hist = self.get_api_transaction_history(date_from, date_to)
        for _, item in trans_hist.iterrows():
            trans = AccountTransactions(account=self.ta,
                                        created_at=item['created_at'].to_pydatetime(),
                                        updated_at=datetime.now(timezone.utc),
                                        asset=item['asset'],
                                        amount=item['amount'],
                                        side=item['side']
                                        )
            try:
                trans.save()
            except IntegrityError as e:
                print(e)

    def load_snapshot_history(self, date_from, date_to, market):
        '''Load snapshots between date_from and date_to in local database.'''
        start = Market.to_timestamp(date_from)
        end = Market.to_timestamp(date_to)

        # get balance history
        hist = self.client.get_account_snapshot(type='SPOT', startTime=start, endTime=end)['snapshotVos']
        snapshots = pd.DataFrame([{'asset': bal['asset'], 
                                   'amount': float(bal['free']) + float(bal['locked']), 
                                   'close_time': snap['updateTime'] + 999}
                                   for snap in hist for bal in snap['data']['balances']])

        deposits = self.get_api_deposit_history(date_from, date_to)
        withdrawals = self.get_api_withdrawal_history(date_from, date_to)

        assets_to_track = set(snapshots['asset']).union(set(deposits['asset'])).union(set(withdrawals['asset']))

        btc_usdt_prices = market.get_price_history('BTC', 'USDT', date_from, date_to, '1d')
        prices = pd.DataFrame(columns=['open_time', 'open_price', 'close_time', 'close_price', 'asset', 'base', 'symbol'])
        for asset in assets_to_track:
            prices = prices.append(market.get_price_history(asset, 'BTC', date_from, date_to, '1d'))

        # get price of each asset in usdt
        prices = prices.merge(btc_usdt_prices, on=['open_time', 'close_time'], suffixes=("_btc", "_usdt"))
        prices['open_price_usdt'] = prices['open_price_btc'] * prices['open_price_usdt']
        prices['close_price_usdt'] = prices['close_price_btc'] * prices['close_price_usdt']
        prices['open_time'] = prices['open_time'].astype(int)
        prices['close_time'] = prices['close_time'].astype(int)
        prices['asset'] = prices['asset_btc']
        prices = prices.drop(columns=['asset_btc', 'asset_usdt', 'base_btc', 'base_usdt', 'symbol_usdt'])

        # compute balances per asset
        stats = snapshots.merge(prices, on=['asset', 'close_time'])
        stats['close_balance_btc'] = stats['amount'] * stats['close_price_btc']
        stats['close_balance_usdt'] = stats['amount'] * stats['close_price_usdt']

        # include deposits and withdrawals of each asset
        deposits = deposits.rename(columns={'amount': 'dep_amount', 'time': 'dep_time'})
        deposits['dep_time'] = deposits['dep_time'].astype(int)
        withdrawals = withdrawals.rename(columns={'amount': 'wit_amount', 'time': 'wit_time'})
        withdrawals['wit_time'] = withdrawals['wit_time'].astype(int)

        deposits = pd.merge_asof(deposits, stats, left_on='dep_time', right_on='open_time', by='asset')
        deposits['deposits_btc'] = deposits['dep_amount'] * deposits['close_price_btc']
        deposits['deposits_usdt'] = deposits['dep_amount'] * deposits['close_price_usdt']
        deposits = deposits[['open_time', 'close_time', 'dep_time', 'dep_amount', 'asset', 'deposits_btc', 'deposits_usdt']]
        stats = stats.merge(deposits, how='left', on=['open_time', 'close_time', 'asset'])

        withdrawals = pd.merge_asof(withdrawals, stats, left_on='wit_time', right_on='open_time', by='asset')
        withdrawals['withdrawals_btc'] = withdrawals['wit_amount'] * withdrawals['close_price_btc']
        withdrawals['withdrawals_usdt'] = withdrawals['wit_amount'] * withdrawals['close_price_usdt']
        withdrawals = withdrawals[['open_time', 'close_time', 'wit_time', 'wit_amount', 'asset', 'withdrawals_btc', 'withdrawals_usdt']]
        stats = stats.merge(withdrawals, how='left', on=['open_time', 'close_time', 'asset'])

        # group results by snapshot time
        stats = stats.fillna(0)
        agg_stats = stats.groupby('close_time').agg({'close_balance_btc': 'sum',
                                                     'close_balance_usdt': 'sum',
                                                     'deposits_btc': 'sum',
                                                     'deposits_usdt': 'sum',
                                                     'withdrawals_btc': 'sum',
                                                     'withdrawals_usdt': 'sum'
                                                     }).reset_index()
        agg_stats = agg_stats.sort_values('close_time')

        # compute PnL 
        agg_stats['open_balance_btc'] = agg_stats['close_balance_btc'].shift(1)
        agg_stats['open_balance_usdt'] = agg_stats['close_balance_usdt'].shift(1)
        agg_stats['pnl_btc'] = agg_stats['close_balance_btc'] - agg_stats['open_balance_btc']\
                             - agg_stats['deposits_btc'] + agg_stats['withdrawals_btc']
        agg_stats['pnl_usdt'] = agg_stats['close_balance_usdt'] - agg_stats['open_balance_usdt']\
                              - agg_stats['deposits_usdt'] + agg_stats['withdrawals_usdt']        
        agg_stats = agg_stats.dropna()

        # record snaps in database
        for stat in agg_stats.itertuples(name='Stat'):
            snap = SnapshotAccount(account=self.ta,
                                   balance_btc=Decimal(stat.close_balance_btc),
                                   balance_usdt=Decimal(stat.close_balance_usdt),
                                   pnl_btc=Decimal(stat.pnl_btc),
                                   pnl_usdt=Decimal(stat.pnl_usdt),
                                   created_at=Market.to_datetime(stat.close_time),
                                   updated_at=datetime.now(timezone.utc)
                                   )
            try:
                snap.save()
                snap_details = snapshots[snapshots['close_time'] == stat.close_time]
                snap_details = snap_details.merge(prices, on=['asset', 'close_time'])
                for item in snap_details.itertuples(name='Snap'):
                    detail = SnapshotAccountDetails(snapshot=snap, 
                                                    asset=item.asset, 
                                                    amount=Decimal(item.amount),
                                                    price_usdt=Decimal(item.close_price_usdt),
                                                    price_btc=Decimal(item.close_price_btc)
                                                    )
                    try:
                        detail.save()
                    except IntegrityError as e:
                        print(e)

            except IntegrityError as e: 
                print(e)


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