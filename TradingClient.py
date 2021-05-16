import pandas as pd
from datetime import datetime, timedelta, timezone
from abc import ABC, abstractmethod
from binance.client import Client as BinanceClient
from Market import Market
from django.db.models.functions import TruncDay
from django.db.models import Avg, Sum
from traderboard.models import SnapshotAccount, SnapshotAccountDetails

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

    def get_daily_balances(self, date_from, date_to, base='USDT'):
        '''Returns a historical balance time series aggregated by day'''
        snaps = SnapshotAccount.objects.filter(account=self.ta)\
                                       .filter(created_at__range=[date_from, date_to])\
                                       .annotate(day=TruncDay('created_at'))\
                                       .values('day')\
                                       .annotate(balance_usdt=Avg('balance_usdt'))\
                                       .annotate(balance_btc=Avg('balance_btc'))\
                                       .order_by('day')

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
        '''Returns a historical PnL time series aggregated by day'''
        snaps = SnapshotAccount.objects.filter(account=self.ta)\
                                       .filter(created_at__range=[date_from, date_to])\
                                       .annotate(day=TruncDay('created_at'))\
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

    def get_balance_history(self, date_from, date_to, market):
        # complete using get_order_history
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

    def get_order_history(self, date_from, snap, market):
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(snap.created_at)
        balances = SnapshotAccountDetails.objects.filter(snapshot=snap)
        balances = pd.DataFrame.from_records(balances.values('asset', 'amount'))
        orders =  pd.DataFrame(columns=['time', 'asset', 'amount', 'base', 'price', 'side'])
        for _, bal in balances.iterrows():
            symbols = market.table[market.table['symbol'].str.startswith(bal['asset'])]['symbol']
            for symbol in symbols:
                orders_symbol = self.client.get_all_orders(symbol=symbol, limit=1000)
                orders_symbol = pd.DataFrame(orders_symbol)
                if not orders_symbol.empty:
                    orders_symbol = orders_symbol[orders_symbol["time"].between(start, end)]
                    orders_symbol['asset'] = bal['asset']
                    orders_symbol['base'] = symbol.split(bal['asset'], 1)[1]
                    orders_symbol['amount'] = orders_symbol['executedQty'].astype(float)
                    orders_symbol['price'] = orders_symbol['price'].astype(float)
                    orders_symbol = orders_symbol[['time', 'asset', 'amount', 'base', 'price', 'side']]
                    orders = orders.append(orders_symbol, ignore_index=True)
        return orders

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

    def load_past_stats(self, date_from, market):
        '''This method should be only triggered when a user registers a new 
        Binance trading account to the website'''
        # load stats from date_from until now
        date_to = datetime.now(timezone.utc)
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)

        # get balance history
        hist = self.client.get_account_snapshot(type='SPOT', startTime=start, endTime=end)['snapshotVos']
        btc_bal = pd.DataFrame(
                        [{'timestamp': snap['updateTime'], 'balance_btc': float(snap['data']['totalAssetOfBtc'])}
                        for snap in hist])
        btc_bal['date'] = btc_bal['timestamp'].apply(lambda ts: market.to_date(ts))
        btc_usdt_prices = market.get_daily_prices('BTC', 'USDT', date_from, date_to)

        stats = btc_bal.merge(btc_usdt_prices, 'inner', left_on='date', right_on='close_date')
        stats['balance_usdt'] = stats['balance_btc'] * stats['close_price']
        stats['balance_usdt_open'] = stats['balance_usdt'].shift(1)
        stats['balance_btc_open'] = stats['balance_btc'].shift(1)
        stats['pnl_usdt'] = stats['balance_usdt'] - stats['balance_usdt_open']
        stats['pnl_btc'] = stats['balance_btc'] - stats['balance_btc_open']
        stats = stats[['date', 'balance_btc', 'balance_usdt', 'pnl_usdt', 'pnl_btc']]
        
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
                stats = stats.fillna({'deposit_value_btc': 0.0, 'deposit_value_usdt': 0.0})

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
                stats = stats.fillna({'withdrawal_value_btc': 0.0, 'withdrawal_value_usdt': 0.0})

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
