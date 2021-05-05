from datetime import datetime, timezone
from abc import ABC, abstractmethod
from binance.client import Client as BinanceClient
from multipledispatch import dispatch
import pandas as pd


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
    def get_timestamp_offset(self) -> int:
        pass

    @abstractmethod
    def to_timestamp(self, date: datetime) -> int:
        pass

    @abstractmethod
    def to_datetime(self, timestamp: int) -> datetime:
        pass

    @abstractmethod
    def to_date(self, timestamp: int) -> datetime:
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
        self.bases = ['USDT', 'BTC', 'ETH', 'BNB']
        self.timestamp_offset = self.get_timestamp_offset()
    
    def get_timestamp_offset(self):
        '''Return offset between API server time and UTC timezone'''
        server_time = self.client.get_server_time()['serverTime'] # in ms
        now = datetime.now(timezone.utc).timestamp()
        offset = server_time - int(now * 1000)
        return offset

    def to_timestamp(self, dt):
        # convert server time to UTC time, in ms
        ts = int(dt.timestamp() * 1000 + self.timestamp_offset)
        return ts

    @dispatch(int)
    def to_datetime(self, timestamp):
        # convert server timestamp to UTC datetime object
        ts = timestamp / 1000 # convert is seconds
        dt = datetime.fromtimestamp(ts, timezone.utc)
        return dt

    @dispatch(str)
    def to_datetime(self, dt):
        # convert str date to UTC datetime object
        dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @dispatch(str)
    def to_date(self, dt):
        # convert str date to UTC datetime object
        dt = self.to_datetime(dt)
        return datetime.combine(dt, datetime.min.time(), timezone.utc)

    @dispatch(int)
    def to_date(self, timestamp):
        # convert server timestamp to UTC date-like object
        date = self.to_datetime(timestamp)
        return datetime.combine(date, datetime.min.time(), timezone.utc)      

    def get_price_table(self):
        '''Return current market price table'''
        prices = self.client.get_all_tickers()
        price_table = pd.DataFrame(prices)
        price_table = price_table.astype({"price": float})
        return price_table