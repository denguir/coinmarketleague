from datetime import datetime, timezone
from abc import ABC, abstractmethod
from binance.client import Client as BinanceClient
from binance.exceptions import BinanceAPIException
from multipledispatch import dispatch
import pandas as pd
import numpy as np


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
    
    @dispatch(datetime)
    def to_timestamp(self, dt):
        # convert server time to UTC time, in ms
        ts = int(dt.timestamp() * 1000 + self.timestamp_offset)
        return ts

    @dispatch(str)
    def to_timestamp(self, dt):
        dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        return self.to_timestamp(dt)

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

    def round_date(self, date, interval):
        if interval == '1m':
            date = date.replace(microsecond=0, second=0, tzinfo=timezone.utc)
        elif interval == '1h':
            date = date.replace(microsecond=0, second=0, minute=0, tzinfo=timezone.utc)
        elif interval == '1d':
            date = date.replace(microsecond=0, second=0, minute=0, hour=0, tzinfo=timezone.utc)
        return date

    def timestamp_range(self, date_from, date_to, interval):
        start = self.round_date(date_from, interval)
        end = self.round_date(date_to, interval)
        ts = pd.date_range(start=start, end=end, freq=interval)
        ts = ts.astype(np.int64) // 10 ** 6
        return ts

    def get_price_table(self):
        '''Return current market price table'''
        prices = self.client.get_all_tickers()
        price_table = pd.DataFrame(prices)
        price_table = price_table.astype({"symbol": str, "price": float})

        symbol_info = self.client.get_exchange_info()['symbols']
        symbol_cols = ['symbol', 'baseAsset', 'quoteAsset', 'baseAssetPrecision', 'quoteAssetPrecision']
        symbol_info = [{key: info[key] for key in symbol_cols} for info in symbol_info]
        symbol_table = pd.DataFrame(symbol_info)

        price_table = price_table.merge(symbol_table, on='symbol')
        return price_table.drop_duplicates()
    
    def get_price(self, asset, base):
        '''Return price of asset w.r.t base'''
        assert base in self.bases, f"{base} not supported as an exchange base."
        if asset == base:
            price = 1.0
        else:
            symbol = asset + base
            res = self.table[self.table['symbol'] == symbol]
            if res.empty:
                symbol = base + asset
                res = self.table[self.table['symbol'] == symbol]
                if res.empty:
                    other_symbols = [asset + other_base for other_base in self.bases]
                    others = self.table[self.table['symbol'].isin(other_symbols)]
                    if others.empty:
                        print(f"Asset {asset} seems to have no exchange with one of the supported bases {self.bases}.")
                        price = 0.0
                    else:
                        alt_symb = others.iloc[0]['symbol']
                        alt_price = others.iloc[0]['price']
                        alt_base = alt_symb.split(asset, 1)[1]
                        price = alt_price * self.get_price(alt_base, base)
                else:
                    price = 1.0 / float(res['price'])
            else:
                price = float(res['price'])
        return price

    def get_price_history(self, asset, base, date_from, date_to, interval):
        '''Return price history of asset w.r.t base between date_from and date_to'''
        assert base in self.bases, f"{base} not supported as an exchange base."
        start = self.to_timestamp(date_from)
        end = self.to_timestamp(date_to)
        prices = pd.DataFrame(columns=['open_time', 'open_price'])
        time_range = pd.DataFrame(self.timestamp_range(date_from, date_to, interval), columns=['open_time'])
        prices['open_time'] = time_range['open_time']
        if asset == base:
            prices['open_price'] = 1.0
        else:
            symbol = asset + base
            try:
                res = self.client.get_klines(symbol=symbol, interval=interval, startTime=start, endTime=end, limit=1000)
                prices = pd.DataFrame(
                        [(int(row[0]), float(row[1])) for row in res], columns=['open_time', 'open_price'])
            except BinanceAPIException:
                symbol = base + asset
                try:
                    res = self.client.get_klines(symbol=symbol, interval=interval, startTime=start, endTime=end, limit=1000)
                    prices = pd.DataFrame(
                        [(int(row[0]), float(row[1])) for row in res], columns=['open_time', 'open_price'])
                    prices['open_price'] = 1.0 / prices['open_price']
                except BinanceAPIException:
                    other_symbols = [asset + other_base for other_base in self.bases]
                    others = self.table[self.table['symbol'].isin(other_symbols)]
                    if others.empty:
                        print(f"Asset {asset} seems to have no exchange with one of the supported bases {self.bases}.")
                        prices['open_price'] = 0.0
                    else:
                        alt_symb = others.iloc[0]['symbol']
                        alt_base = alt_symb.split(asset, 1)[1]
                        try:
                            res = self.client.get_klines(symbol=alt_symb, interval=interval, startTime=start, endTime=end, limit=1000)
                            prices = pd.DataFrame(
                                    [(int(row[0]), float(row[1])) for row in res], columns=['open_time', 'open_price'])
                            prices = prices.merge(self.get_price_history(alt_base, base, date_from, date_to, interval),
                                                'inner', on='open_time')
                            prices['open_price'] = prices['open_price_x'] * prices['open_price_y']
                        except BinanceAPIException:
                            print(f"Asset {asset} seems to have no exchange with base {alt_base}\
                                between {date_from} and {date_to}.")
                            prices['open_price'] = 0.0
        # interpolate prices if wholes in query 
        prices = prices.merge(time_range, how='right', on='open_time')
        prices['open_price'] = prices['open_price'].interpolate(method='linear').fillna(method='backfill')
        prices['asset'] = asset
        prices['base'] = base
        prices['symbol'] = asset + base
        return prices

    def get_daily_prices(self, asset, base, date_from, date_to):
        '''Return daily prices of asset w.r.t base between date_from and date_to'''
        assert base in self.bases, f"{base} not supported as an exchange base."
        start = self.to_timestamp(date_from)
        end = self.to_timestamp(date_to)
        if asset == base:
            prices = pd.DataFrame(columns=['close_date', 'close_price'])
            prices['close_date'] = pd.date_range(start=date_from, end=date_to)
            prices['close_price'] = 1.0
        else:
            symbol = asset + base
            try:
                res = self.client.get_klines(symbol=symbol, interval='1d', startTime=start, endTime=end)
                prices = pd.DataFrame(
                        [(row[6], float(row[4])) for row in res], columns=['close_time', 'close_price'])
                prices['close_date'] = prices['close_time'].apply(lambda ts: self.to_date(ts))
            except BinanceAPIException:
                symbol = base + asset
                try:
                    res = self.client.get_klines(symbol=symbol, interval='1d', startTime=start, endTime=end)
                    prices = pd.DataFrame(
                        [(row[6], float(row[4])) for row in res], columns=['close_time', 'close_price'])
                    prices['close_date'] = prices['close_time'].apply(lambda ts: self.to_date(ts))
                    prices['close_price'] = 1.0 / prices['close_price']
                except BinanceAPIException:
                    other_symbols = [asset + other_base for other_base in self.bases]
                    others = self.table[self.table['symbol'].isin(other_symbols)]
                    if others.empty:
                        print(f"Asset {asset} seems to have no exchange with one of the supported bases {self.bases}.")
                        prices = pd.DataFrame(columns=['close_date', 'close_price'])
                        prices['close_date'] = pd.date_range(start=self.to_date(date_from), end=self.to_date(date_to))
                        prices['close_price'] = 0.0
                    else:
                        alt_symb = others.iloc[0]['symbol']
                        alt_base = alt_symb.split(asset, 1)[1]
                        try:
                            res = self.client.get_klines(symbol=alt_symb, interval='1d', startTime=start, endTime=end)
                            prices = pd.DataFrame(
                                    [(row[6], float(row[4])) for row in res], columns=['close_time', 'close_price'])
                            prices['close_date'] = prices['close_time'].apply(lambda ts: self.to_date(ts))
                            prices = prices.merge(self.get_daily_prices(alt_base, base, date_from, date_to),
                                                'inner', on='close_date')
                            prices['close_price'] = prices['close_price_x'] * prices['close_price_y']
                        except BinanceAPIException:
                            print(f"Asset {asset} seems to have no exchange with base {alt_base}\
                                between {date_from} and {date_to}.")
                            prices = pd.DataFrame(columns=['close_date', 'close_price'])
                            prices['close_date'] = pd.date_range(start=self.to_date(date_from), end=self.to_date(date_to))
                            prices['close_price'] = 0.0
        return prices




