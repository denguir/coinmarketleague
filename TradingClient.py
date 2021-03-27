from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from binance.client import Client as BinanceClient
from traderboard.models import TradingAccount, SnapshotAccount
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
    def get_balances(self) -> list:
        pass

    @abstractmethod
    def get_balances_value(self, price_table: dict, base: str) -> float:
        pass

    @abstractmethod
    def get_deposits(self, date_from: datetime, date_to: datetime, market: Market) -> list:
        pass

    @abstractmethod
    def get_withdrawals(self, date_from: datetime, date_to: datetime, market: Market) -> list:
        pass

    @abstractmethod
    def get_PnL(self, date_from: datetime, date_to: datetime, market: Market) -> float:
        pass

    def get_daily_PnL(self, market: Market) -> float:
        date_from = datetime.today() - timedelta(days=1)
        date_to = datetime.today()
        return self.get_PnL(date_from, date_to, market)

    def get_weekly_PnL(self, market: Market) -> float:
        date_from = datetime.today() - timedelta(days=7)
        date_to = datetime.today()
        return self.get_PnL(date_from, date_to, market)

    def get_monthly_PnL(self, market: Market) -> float:
        date_from = datetime.today() - timedelta(days=31)
        date_to = datetime.today()
        return self.get_PnL(date_from, date_to, market)


class BinanceTradingClient(TradingClient):
    '''Trading client for Binance built from the trading accout
        id of the user'''

    def __init__(self, ta):
        super().__init__(ta)
        self.client = BinanceClient(ta.api_key, ta.api_secret)

    def get_balances(self):
        info = self.client.get_account()
        balances = {bal['asset'] : float(bal['free']) + float(bal['locked']) for bal in info['balances']}
        return balances

    def get_balances_btc_value(self, price_table):
        balances = self.get_balances()
        btc_value = 0.0
        for asset in balances.keys():
            try:
                try:
                    if asset == 'BTC':
                        btc_price = 1.0
                    else:
                        btc_price = price_table[asset + 'BTC']
                except KeyError:
                    btc_price = 1.0 / price_table['BTC' + asset]
            except KeyError:
                # asset not available on platform
                btc_price = 0.0
            btc_value += (balances[asset] * btc_price)
        return btc_value

    def get_balances_value(self, price_table, base='BTC'):
        base = base.upper()
        btc_value = self.get_balances_btc_value(price_table)
        if base == 'BTC':
            market_price = 1.0
        else:
            try:
                market_price = price_table['BTC' + base]
            except KeyError:
                market_price = price_table[base + 'BTC']
        market_value = btc_value * market_price
        return market_value

    def get_deposits(self, date_from, date_to, market):
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        info = self.client.get_deposit_history(startTime=start, endTime=end, status=1)
        return info['depositList']

    def get_withdrawals(self, date_from, date_to, market):
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        info = self.client.get_withdraw_history(startTime=start, endTime=end, status=6)
        return info['withdrawList']

    def get_PnL(self, balance_history, date_from, market):
        pass