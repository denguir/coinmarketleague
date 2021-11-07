from datetime import datetime, timezone
from abc import ABC, abstractmethod
from binance import Client
from binance.exceptions import BinanceAPIException
from multipledispatch import dispatch
from traderboard.models import SnapshotMarket
import pandas as pd
import numpy as np


class BaseMarket:
    '''Provide with all the methods exclusively querying the local database.
       A Market should extend this class to get access to localy stored data.'''
    
    def __init__(self, platform):
        self.platform = platform

    def get_price_table(self, asset, base):
        '''Grab the last Market prices from Market'''
        last_date = SnapshotMarket.objects.latest('created_at').created_at
        prices = SnapshotMarket.objects.filter(created_at=last_date)
        prices = pd.DataFrame.from_records(prices)
        return prices

    def get_klines(self, symbol, interval, startTime, endTime):
        # give same output as get_klines
        # aggregate like in Trader
        pass
    

class BinanceMarket:
    '''Market info for Binance'''
    
    def __init__(self, platform):
        super().__init__()
        self.platform = platform
        self.bases = ['USDT', 'BTC', 'ETH', 'BNB', 'BUSD']
    
    @classmethod
    def connect(cls, platform):
        self = cls(platform)
        self.client = Client(None, None)
        self.timestamp_offset = self.get_timestamp_offset()
        self.table = self.get_price_table()
        return self

    def get_timestamp_offset(self):
        '''Return offset between API server time and UTC timezone'''
        server_time = self.client.get_server_time()
        server_time = server_time['serverTime'] # in ms
        now = datetime.now(timezone.utc).timestamp()
        offset = server_time - int(now * 1000)
        return offset

    def round_date(self, date, interval, mode='open'):
        if interval == '1m':
            if mode == 'open':
                date = date.replace(microsecond=0, second=0, tzinfo=timezone.utc)
            else:
                date = date.replace(microsecond=999999, second=59, tzinfo=timezone.utc)
        elif interval == '1h':
            if mode == 'open':
                date = date.replace(microsecond=0, second=0, minute=0, tzinfo=timezone.utc)
            else:
                date = date.replace(microsecond=999999, second=59, minute=59, tzinfo=timezone.utc)
        elif interval == '1d':
            if mode == 'open':
                date = date.replace(microsecond=0, second=0, minute=0, hour=0, tzinfo=timezone.utc)
            else:
                date = date.replace(microsecond=999999, second=59, minute=59, hour=23, tzinfo=timezone.utc)
        return date

    def get_timestamp_range(self, date_from, date_to, interval, mode='open'):
        start = self.round_date(date_from, interval, mode)
        end = self.round_date(date_to, interval, mode)
        ts = pd.date_range(start=start, end=end, freq=interval)
        ts = ts.astype(np.int64) // 10 ** 6
        return ts

    def get_price_table(self):
        '''Return current market price table'''
        prices = self.client.get_ticker()
        price_table = pd.DataFrame(prices)
        price_table['price'] = price_table['lastPrice']
        price_table = price_table.astype({"symbol": str, 
                                          "lastPrice": float,
                                          "openPrice": float,
                                          "highPrice": float,
                                          "lowPrice": float})

        symbol_info = self.client.get_exchange_info()
        symbol_info = symbol_info['symbols']
        symbol_cols = ['symbol', 'baseAsset', 'quoteAsset', 'baseAssetPrecision', 'quoteAssetPrecision']
        symbol_info = [{key: info[key] for key in symbol_cols} for info in symbol_info]
        symbol_table = pd.DataFrame(symbol_info)

        price_table = price_table.merge(symbol_table, on='symbol')
        return price_table.drop_duplicates()
    
    def get_price(self, asset, base):
        '''Return price of asset w.r.t base'''
        assert base in self.bases, f"{base} not supported as an exchange base."
        if asset == base:
            price = {"lastPrice": 1.0, 
                     "openPrice": 1.0, 
                     "highPrice": 1.0, 
                     "lowPrice": 1.0}
        else:
            symbol = asset + base
            res = self.table[(self.table['symbol'] == symbol) & (self.table['lastId'] > 0)]
            if res.empty:
                symbol = base + asset
                res = self.table[(self.table['symbol'] == symbol) & (self.table['lastId'] > 0)]
                if res.empty:
                    other_symbols = [asset + other_base for other_base in self.bases]
                    others = self.table[(self.table['symbol'].isin(other_symbols)) & (self.table['lastId'] > 0)]
                    if others.empty:
                        print(f"Asset {asset} seems to have no exchange with one of the supported bases {self.bases}.")
                        price = {"lastPrice": 0.0, 
                                 "openPrice": 0.0, 
                                 "highPrice": 0.0, 
                                 "lowPrice": 0.0}
                    else:
                        alt_base = others.iloc[0]['quoteAsset']
                        alt_price = others.iloc[0][['lastPrice', 'openPrice', 'highPrice', 'lowPrice']].to_dict()
                        base_price = self.get_price(alt_base, base)
                        price = {k: alt_price[k] * base_price[k] for k in alt_price.keys()}
                else:
                    price = {"lastPrice": 1.0 / float(res['lastPrice']), 
                             "openPrice": 1.0 / float(res['openPrice']), 
                             "highPrice": 1.0 / float(res['highPrice']), 
                             "lowPrice": 1.0 / float(res['lowPrice'])}
            else:
                price = {"lastPrice": float(res['lastPrice']), 
                         "openPrice": float(res['openPrice']), 
                         "highPrice": float(res['highPrice']), 
                         "lowPrice": float(res['lowPrice'])}
        return price

    def get_price_history(self, asset, base, date_from, date_to, interval):
        '''Return price history of asset w.r.t base between date_from and date_to'''
        assert base in self.bases, f"{base} not supported as an exchange base."
        start = Market.to_timestamp(self.round_date(date_from, interval, 'open'))
        end = Market.to_timestamp(self.round_date(date_to, interval, 'close'))
        prices = pd.DataFrame(columns=['open_time', 'open_price'])
        time_range = pd.DataFrame({
                     'open_time': self.get_timestamp_range(date_from, date_to, interval, 'open'),
                     'close_time': self.get_timestamp_range(date_from, date_to, interval, 'close')
                    })
        prices['open_time'] = time_range['open_time']
        prices['close_time'] = time_range['close_time']
        if asset == base:
            prices['open_price'] = 1.0
            prices['close_price'] = 1.0
        else:
            symbol = asset + base
            try:
                res = self.client.get_klines(symbol=symbol, interval=interval, startTime=start, endTime=end, limit=1000)
                prices = pd.DataFrame(
                            [(int(row[0]), float(row[1]), int(row[6]), float(row[4])) for row in res], 
                            columns=['open_time', 'open_price', 'close_time', 'close_price'])
            except BinanceAPIException:
                symbol = base + asset
                try:
                    res = self.client.get_klines(symbol=symbol, interval=interval, startTime=start, endTime=end, limit=1000)
                    prices = pd.DataFrame(
                                [(int(row[0]), float(row[1]), int(row[6]), float(row[4])) for row in res], 
                                columns=['open_time', 'open_price', 'close_time', 'close_price'])
                    prices['open_price'] = 1.0 / prices['open_price']
                    prices['close_price'] = 1.0 / prices['close_price']
                except BinanceAPIException:
                    other_symbols = [asset + other_base for other_base in self.bases]
                    others = self.table[self.table['symbol'].isin(other_symbols)]
                    if others.empty:
                        print(f"Asset {asset} seems to have no exchange with one of the supported bases {self.bases}.")
                        prices['open_price'] = 0.0
                        prices['close_price'] = 0.0
                    else:
                        alt_symb = others.iloc[0]['symbol']
                        alt_base = alt_symb.split(asset, 1)[1]
                        try:
                            res = self.client.get_klines(symbol=alt_symb, interval=interval, startTime=start, endTime=end, limit=1000)
                            prices = pd.DataFrame(
                                        [(int(row[0]), float(row[1]), int(row[6]), float(row[4])) for row in res], 
                                        columns=['open_time', 'open_price', 'close_time', 'close_price'])
                            price_hist = self.get_price_history(alt_base, base, date_from, date_to, interval)
                            prices = prices.merge(price_hist, 'inner', on=['open_time', 'close_time'])
                            prices['open_price'] = prices['open_price_x'] * prices['open_price_y']
                            prices['close_price'] = prices['close_price_x'] * prices['close_price_y']
                        except BinanceAPIException:
                            print(f"Asset {asset} seems to have no exchange with base {alt_base}\
                                between {date_from} and {date_to}.")
                            prices['open_price'] = 0.0
                            prices['close_price'] = 0.0
        # interpolate prices if wholes in query 
        prices = prices.merge(time_range, how='right', on=['open_time', 'close_time'])
        prices['open_price'] = prices['open_price'].interpolate(method='linear').fillna(method='backfill')
        prices['close_price'] = prices['close_price'].interpolate(method='linear').fillna(method='backfill')
        prices['asset'] = asset
        prices['base'] = base
        prices['symbol'] = asset + base
        return prices

    def get_daily_prices(self, asset, base, date_from, date_to):
        '''Return daily prices of asset w.r.t base between date_from and date_to'''
        assert base in self.bases, f"{base} not supported as an exchange base."
        start = Market.to_timestamp(date_from)
        end = Market.to_timestamp(date_to)
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
                prices['close_date'] = prices['close_time'].apply(lambda ts: Market.to_date(ts))
            except BinanceAPIException:
                symbol = base + asset
                try:
                    res = self.client.get_klines(symbol=symbol, interval='1d', startTime=start, endTime=end)
                    prices = pd.DataFrame(
                        [(row[6], float(row[4])) for row in res], columns=['close_time', 'close_price'])
                    prices['close_date'] = prices['close_time'].apply(lambda ts: Market.to_date(ts))
                    prices['close_price'] = 1.0 / prices['close_price']
                except BinanceAPIException:
                    other_symbols = [asset + other_base for other_base in self.bases]
                    others = self.table[self.table['symbol'].isin(other_symbols)]
                    if others.empty:
                        print(f"Asset {asset} seems to have no exchange with one of the supported bases {self.bases}.")
                        prices = pd.DataFrame(columns=['close_date', 'close_price'])
                        prices['close_date'] = pd.date_range(start=Market.to_date(date_from), end=Market.to_date(date_to))
                        prices['close_price'] = 0.0
                    else:
                        alt_symb = others.iloc[0]['symbol']
                        alt_base = alt_symb.split(asset, 1)[1]
                        try:
                            res = self.client.get_klines(symbol=alt_symb, interval='1d', startTime=start, endTime=end)
                            prices = pd.DataFrame(
                                    [(row[6], float(row[4])) for row in res], columns=['close_time', 'close_price'])
                            prices['close_date'] = prices['close_time'].apply(lambda ts: Market.to_date(ts))
                            price_hist = self.get_daily_prices(alt_base, base, date_from, date_to)
                            prices = prices.merge(price_hist, 'inner', on='close_date')
                            prices['close_price'] = prices['close_price_x'] * prices['close_price_y']
                        except BinanceAPIException:
                            print(f"Asset {asset} seems to have no exchange with base {alt_base}\
                                between {date_from} and {date_to}.")
                            prices = pd.DataFrame(columns=['close_date', 'close_price'])
                            prices['close_date'] = pd.date_range(start=Market.to_date(date_from), end=Market.to_date(date_to))
                            prices['close_price'] = 0.0
        return prices


class Market:
    def __init__(self):
        self._markets = {
            'Binance': BinanceMarket,
        }
    
    @classmethod
    def connect(cls, platform):
        self = cls()
        market = self._markets[platform]
        if not market:
            raise ValueError(f'Platform not supported - {platform}')
        return market.connect(platform)

    @staticmethod
    @dispatch(datetime)
    def to_timestamp(dt):
        # convert server time to UTC time, in ms
        ts = int(dt.timestamp() * 1000)
        return ts

    @staticmethod
    @dispatch(str)
    def to_timestamp(dt):
        dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        return Market.to_timestamp(dt)

    @staticmethod
    @dispatch(int)
    def to_datetime(timestamp):
        # convert server timestamp to UTC datetime object
        ts = timestamp / 1000 # convert is seconds
        dt = datetime.fromtimestamp(ts, timezone.utc)
        return dt

    @staticmethod
    @dispatch(str)
    def to_datetime(dt):
        # convert str date to UTC datetime object
        dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    @dispatch(str)
    def to_date(dt):
        # convert str date to UTC datetime object
        dt = Market.to_datetime(dt)
        return datetime.combine(dt, datetime.min.time(), timezone.utc)

    @staticmethod
    @dispatch(int)
    def to_date(timestamp):
        # convert server timestamp to UTC date-like object
        date = Market.to_datetime(timestamp)
        return datetime.combine(date, datetime.min.time(), timezone.utc)         


