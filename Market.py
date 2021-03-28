from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from binance.client import Client as BinanceClient

__PLATFORMS__ = ['Binance']

class Market(ABC):
    '''Abstract class for Market. Each platform market
        must inherit from this class.
    - base: base coin of comparison (BTC, USDT)'''

    @staticmethod
    def trading_from(platform):
        assert(platform in __PLATFORMS__)
        if platform == 'Binance':
            return BinanceMarket(platform)

    @abstractmethod
    def __init__(self, platform):
        self.platform = platform
        
    @abstractmethod
    def to_timestamp(self, date: datetime) -> int:
        pass

    @abstractmethod
    def get_price_table(self) -> dict:
        pass


class BinanceMarket(Market):
    '''Market info for Binance'''
    
    def __init__(self, platform):
        super().__init__(platform)
        self.client = BinanceClient(None, None)
        self.table = self.get_price_table()
    
    def to_timestamp(self, date):
        # convert server time to UTC time, in ms
        ts = int(date.timestamp() * 1000 + self.client.timestamp_offset)
        return ts

    def get_price_table(self):
        prices = self.client.get_all_tickers()
        price_table = {pair['symbol'] : float(pair['price']) for pair in prices}
        return price_table