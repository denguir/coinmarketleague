import pandas as pd
from datetime import datetime
from abc import ABC, abstractmethod
from binance.client import Client as BinanceClient
from Market import Market

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
    def get_deposits(self, date_from: datetime, date_to: datetime, market: Market) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_withdrawals(self, date_from: datetime, date_to: datetime, market: Market) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_value_table(self, balances: pd.DataFrame, market: Market, base: str) -> pd.DataFrame:
        pass


class BinanceTradingClient(TradingClient):
    '''Trading client for Binance built from the trading accout
        id of the user'''
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

    def get_deposits(self, date_from, date_to, market):
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
        print(deposits)
        return deposits

    def get_withdrawals(self, date_from, date_to, market):
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
        print(withdrawals)
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
        assert('time' in balances.columns, "Input DataFrame needs time col.")
        mkt = self.get_value_table(balances, market, base)
        mkt['day'] = mkt['time'].apply(market.to_date)
        return mkt.groupby('day')['value'].sum().to_dict()

    def get_balances_value(self, market, base='USDT'):
        balances = self.get_balances()
        return self.get_value(balances, market, base)

    def get_deposits_value(self, date_from, date_to, market, base='USDT'):
        deposits = self.get_deposits(date_from, date_to, market)
        return self.get_value(deposits, market, base)

    def get_daily_deposits_value(self, date_from, date_to, market, base='USDT'):
        deposits = self.get_deposits(date_from, date_to, market)
        return self.get_daily_value(deposits, market, base)

    def get_withdrawals_value(self, date_from, date_to, market, base='USDT'):
        withdrawals = self.get_withdrawals(date_from, date_to, market)
        return self.get_value(withdrawals, market, base)

    def get_daily_withdrawals_value(self, date_from, date_to, market, base='USDT'):
        withdrawals = self.get_withdrawals(date_from, date_to, market)
        return self.get_daily_value(withdrawals, market, base)


