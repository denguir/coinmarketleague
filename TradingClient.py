import pandas as pd
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from multipledispatch import dispatch
from binance.client import Client as BinanceClient
from Market import Market
from django.db.models.functions import TruncDay
from django.db.models import Max, Sum
from traderboard.models import SnapshotAccount

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
    def load_stats(self, date_from: datetime):
        pass

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

    def load_stats(self, date_from, market):
        # load stats from date_from until now
        date_to = datetime.now(timezone.utc)
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        hist = self.client.get_account_snapshot(type='SPOT', startTime=start, endTime=end)['snapshotVos']
        btc_bal = pd.DataFrame(
                        [{'timestamp': snap['updateTime'], 'balance_btc': float(snap['data']['totalAssetOfBtc'])}
                        for snap in hist])
        btc_bal['date'] = btc_bal['timestamp'].apply(lambda ts: market.to_date(ts))
        klines = self.client.get_klines(symbol='BTCUSDT', interval='1d', startTime=start, endTime=end)
        prices = pd.DataFrame(
                        [(row[6], float(row[4])) for row in klines], columns=['close_time', 'close_price'])
        prices['close_date'] = prices['close_time'].apply(lambda ts: market.to_date(ts))

        bal = btc_bal.merge(prices, 'inner', left_on='date', right_on='close_date')
        bal['balance_usdt'] = bal['balance_btc'] * bal['close_price']
        bal = bal[['date', 'balance_btc', 'balance_usdt']]

        # get pnl
        dep = self.get_deposit_history(date_from, date_to, market)
        wit = self.get_withdrawal_history(date_from, date_to, market)
        
        


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
                                       .filter(created_at__range=[date_from, date_to])\
                                       .annotate(day=TruncDay('created_at'))
        close_time = snaps.values('day')\
                          .annotate(close_time=Max('created_at'))\
                          .values('close_time')

        snaps = snaps.filter(created_at__in=close_time).order_by('day')
        balances = snaps.values('day', 'balance_btc', 'balance_usdt')
        balance_hist = pd.DataFrame.from_records(balances)

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
        '''Returns a historical PnL time series aggregated by day'''
        snaps = SnapshotAccount.objects.filter(account=self.ta)\
                                       .filter(created_at__range=[date_from, date_to])\
                                       .annotate(day=TruncDay('created_at'))\
                                       .values('day')

        pnl = snaps.annotate(pnl_btc=Sum('pnl_btc'))\
                   .annotate(pnl_usdt=Sum('pnl_usdt'))\
                   .order_by('day')

        pnl_hist = pd.DataFrame.from_records(pnl)

        if pnl_hist.empty:
            pnl_hist = pd.DataFrame(columns=['day', 'pnl'])
        else:
            if base == 'BTC':
                pnl_hist['pnl'] = pnl_hist['pnl_btc'].astype(float)
            else:
                pnl_hist['pnl'] = pnl_hist['pnl_usdt'].astype(float)

            pnl_hist = pnl_hist[['day', 'pnl']].fillna({'pnl': 0.0})
        return pnl_hist

    def get_balance_history(self, date_from, date_to, market):
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        info = self.client.get_account_snapshot(type='SPOT', startTime=start, endTime=end)
        pass

    def get_deposit_history(self, date_from, date_to, market):
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        info = self.client.get_deposit_history(startTime=start, endTime=end, status=1)
        deposits = pd.DataFrame(columns=['time', 'asset', 'amount'])
        if info:
            deposits = pd.DataFrame(info)
            deposits['time'] = deposits['insertTime']
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
            withdrawals['time'] = withdrawals['applyTime']
            withdrawals['asset'] = withdrawals['coin']
            withdrawals['amount'] = withdrawals['amount'].astype(float)
            withdrawals = withdrawals[['time', 'asset', 'amount']]
        return withdrawals

    def get_value_table(self, balances, market, base='USDT'):
        '''Compute the value of a balances, deposits or withdrawals DataFrame
            using the market price. We search for the symbol assetBASE and the reverse
            symbol BASEasset in case the former does not exist'''
        symbol = 'asset' + base
        reverse_symbol = base + 'asset'
        balances[symbol] = balances['asset'].apply(lambda x: x + base)
        balances[reverse_symbol] = balances['asset'].apply(lambda x: base + x)
        mkt = balances.merge(market.table, how='left', left_on=symbol, right_on='symbol')
        mkt.loc[mkt[symbol] == base + base, 'price'] = 1.0
        mkt = mkt[mkt['price'].notna()]
        reverse_mkt = balances.merge(market.table, how='left', left_on=reverse_symbol, right_on='symbol')
        reverse_mkt = reverse_mkt[reverse_mkt['price'].notna()]
        reverse_mkt['price'] = 1.0 / reverse_mkt['price']
        mkt = pd.concat([mkt, reverse_mkt])
        mkt['value'] = mkt['amount'] * mkt['price']
        return mkt

    def get_per_quote_value_table(self, balances, market, base, quote):
        pass


    def get_value(self, balances, market, base='USDT'):
        '''Return the sum of the value table of either a
        deposits, withdrawals or balances dataFrame'''
        mkt = self.get_value_table(balances, market, base)
        return sum(mkt['value'])

    def get_daily_value(self, balances, market, base='USDT'):
        '''Return the daily aggregated sum of the value table of time-aware
        DataFrame -> either a deposits or withdrawals dataFrame'''
        assert 'time' in balances.columns, "Input DataFrame needs time col."
        mkt = self.get_value_table(balances, market, base)
        mkt['day'] = mkt['time'].apply(market.to_date)
        return mkt.groupby('day')['value'].sum().to_dict()

    def get_balances_value(self, market, base='USDT'):
        balances = self.get_balances()
        return self.get_value(balances, market, base)

    def get_deposits_value(self, date_from, date_to, market, base='USDT'):
        deposits = self.get_deposit_history(date_from, date_to, market)
        return self.get_value(deposits, market, base)

    def get_daily_deposits_value(self, date_from, date_to, market, base='USDT'):
        deposits = self.get_deposit_history(date_from, date_to, market)
        return self.get_daily_value(deposits, market, base)

    def get_withdrawals_value(self, date_from, date_to, market, base='USDT'):
        withdrawals = self.get_withdrawal_history(date_from, date_to, market)
        return self.get_value(withdrawals, market, base)

    def get_daily_withdrawals_value(self, date_from, date_to, market, base='USDT'):
        withdrawals = self.get_withdrawal_history(date_from, date_to, market)
        return self.get_daily_value(withdrawals, market, base)


