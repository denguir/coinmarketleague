from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from binance.client import Client as BinanceClient
from Market import Market


__PLATFORMS__ = ['Binance']


class TradingAccount(ABC):
    '''Abstract Trading account class to inherit from
     to integrate a trading account in a new exchange platform'''

    @staticmethod
    def trading_from(platform, **kwargs):
        assert(platform in __PLATFORMS__)
        if platform == 'Binance':
            return BinanceTradingAccount(**kwargs)

    @abstractmethod
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    def get_api_key(self) -> str:
        pass
    
    @abstractmethod
    def get_api_secret(self) -> str:
        pass

    @abstractmethod
    def get_balances(self) -> list:
        pass

    @abstractmethod
    def get_balances_value(self, market: Market) -> float:
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


class BinanceTradingAccount(TradingAccount):
    '''Trading account for Binance'''

    def __init__(self, api_key, api_secret):
        super().__init__(api_key, api_secret)
        self.platform = 'Binance'
        self.client = BinanceClient(self.api_key, self.api_secret)

    def __str__(self):
        return self.platform

    def get_api_key(self):
        return 0

    def get_api_secret(self):
        return 0

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

    def get_balances_value(self, market):
        price_table = market.get_price_table()
        btc_value = self.get_balances_btc_value(price_table)
        if market.base == 'BTC':
            market_price = 1.0
        else:
            try:
                market_price = price_table['BTC' + market.base]
            except KeyError:
                market_price = price_table[market.base + 'BTC']
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

    def get_PnL(self, date_from, date_to, market):
        pass


if __name__ == '__main__':
    api_key = None
    api_secret = None
    ta = TradingAccount.trading_from('Binance', api_key=api_key, api_secret=api_secret)
    market = Market.trading_from('Binance', base='BTC')
    bal = ta.get_balances_value(market)
    print(bal)