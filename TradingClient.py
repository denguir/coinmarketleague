import pandas as pd
from datetime import datetime
from abc import ABC, abstractmethod
from binance.client import Client as BinanceClient
from traderboard.models import SnapshotAccount
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
    def get_balances(self) -> dict:
        pass

    @abstractmethod
    def get_relative_balances(self, market: Market) -> dict:
        pass

    @abstractmethod
    def get_value(self, balances: dict, market: Market, base: str) -> float:
        pass

    @abstractmethod
    def get_deposits(self, date_from: datetime, date_to: datetime, market: Market) -> list:
        pass

    @abstractmethod
    def get_withdrawals(self, date_from: datetime, date_to: datetime, market: Market) -> list:
        pass

    @abstractmethod
    def get_PnL(self, snap_from: SnapshotAccount, snap_to: SnapshotAccount, market: Market, base: str) -> float:
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
        balances = {bal['asset'] : float(bal['free']) + float(bal['locked']) for bal in info['balances']}
        return balances

    def get_deposits(self, date_from, date_to, market):
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        info = self.client.get_deposit_history(startTime=start, endTime=end, status=1)['depositList']
        deposits = pd.DataFrame(info)
        return deposits.groupby(['asset'])['amount'].sum().to_dict()

    def get_daily_deposits(self, date_from, date_to, market):
        # daily aggregated deposits
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        deposits = self.client.get_deposit_history(startTime=start, endTime=end, status=1)['depositList']
        df = pd.DataFrame(deposits)
        df['date'] = df['insertTime'].apply(market.to_date)
        deposits = df.groupby(['date', 'asset'])['amount'].sum().to_dict()
        return deposits

    def get_withdrawals(self, date_from, date_to, market):
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        info = self.client.get_withdraw_history(startTime=start, endTime=end, status=6)['withdrawList']
        withdrawals = pd.DataFrame(info)
        return withdrawals.groupby(['asset'])['amount'].sum().to_dict()

    def get_asset_btc_value(self, asset, market):
        try:
            try:
                if asset == 'BTC':
                    btc_price = 1.0
                else:
                    btc_price = market.table[asset + 'BTC']
            except KeyError:
                btc_price = 1.0 / market.table['BTC' + asset]
        except KeyError:
            # asset not available on platform
            btc_price = 0.0
        return btc_price

    def get_asset_value(self, asset, market, base='USDT'):
        base = base.upper()
        btc_value = self.get_asset_btc_value(asset, market)
        if base == 'BTC':
            market_price = 1.0
        else:
            try:
                market_price = market.table['BTC' + base]
            except KeyError:
                market_price = market.table[base + 'BTC']
        market_value = btc_value * market_price
        return market_value
           
    def get_value(self, balances, market, base='USDT'):
        # balances is a dict of the form {asset: amount}:
        # could be balances, deposits, withdrawals
        value = 0.0
        for asset in balances.keys():
            value += (balances[asset] * self.get_asset_value(asset, market, base))
        return value
    
    def get_relative_balances(self, market, base='USDT'):
        balances = self.get_balances()
        total_value = self.get_value(balances, market, base)
        for asset, amount in balances.items():
            val = self.get_asset_value(asset, market, base)
            balances[asset] = amount * val / total_value
        return balances

    def get_balances_value(self, market, base='USDT'):
        balances = self.get_balances()
        return self.get_value(balances, market, base)

    def get_deposits_value(self, date_from, date_to, market, base='USDT'):
        deposits = self.get_deposits(date_from, date_to, market)
        return self.get_value(deposits, market, base)
    
    def get_withdrawals_value(self, date_from, date_to, market, base='USDT'):
        withdrawals = self.get_withdrawals(date_from, date_to, market)
        return self.get_value(withdrawals, market, base)

    def get_PnL(self, snap_from, snap_to, market, base='USDT'):
        if base == 'BTC':
            balance_from = snap_from.balance_btc
            balance_to = snap_to.balance_btc
        else:
            balance_from = snap_from.balance_usdt
            balance_to = snap_to.balance_usdt
        
        deposits = self.get_deposits_value(snap_from.created_at, snap_to.created_at, market, base)
        withdrawals = self.get_withdrawals_value(snap_from.created_at, snap_to.created_at, market, base)
        pnl = (balance_to - deposits + withdrawals - balance_from) / balance_from
        return pnl


