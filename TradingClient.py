import pandas as pd
from datetime import datetime, timedelta, timezone
from abc import ABC, abstractmethod
from binance.client import Client as BinanceClient
from Market import Market
from django.db.models.functions import TruncDay
from django.db.models import Max, Sum
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
                                       .annotate(day=TruncDay('created_at'))\
                                       .filter(day__range=[date_from, date_to])
        close_time = snaps.values('day')\
                          .annotate(close_time=Max('created_at'))\
                          .values('close_time')

        snaps = snaps.filter(created_at__in=close_time).order_by('day')
        snaps = snaps.values('day', 'balance_btc', 'balance_usdt')
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
                                       .annotate(day=TruncDay('created_at'))\
                                       .filter(day__range=[date_from, date_to])\
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

    def get_deposit_history(self, date_from, date_to, market):
        start = market.to_timestamp(date_from)
        end = market.to_timestamp(date_to)
        info = self.client.get_deposit_history(startTime=start, endTime=end, status=1)
        deposits = pd.DataFrame(columns=['time', 'asset', 'amount'])
        if info:
            deposits = pd.DataFrame(info)
            deposits['time'] = deposits['insertTime'].apply(lambda x: market.to_timestamp(x))
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
            withdrawals['time'] = withdrawals['applyTime'].apply(lambda x: market.to_timestamp(x))
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
                info = self.client.get_all_orders(symbol=symbol, limit=1000)
                if info:
                    orders_symbol = pd.DataFrame(info)
                    orders_symbol = orders_symbol[orders_symbol["status"].isin(['FILLED', 'PARTIALLY_FILLED'])]
                    orders_symbol = orders_symbol[orders_symbol["time"].between(start, end)]
                    orders_symbol['asset'] = bal['asset']
                    orders_symbol['base'] = symbol.split(bal['asset'], 1)[1]
                    orders_symbol['amount'] = orders_symbol['executedQty'].astype(float)
                    orders_symbol['price'] = orders_symbol['price'].astype(float)
                    orders_symbol = orders_symbol[['time', 'asset', 'amount', 'base', 'price', 'side']]
                    orders = orders.append(orders_symbol, ignore_index=True)
        return orders

    def get_balance_history(self, date_from, snap, market, interval='1h'):
        date_to = snap.created_at
        orders = self.get_order_history(date_from, snap, market)
        orders['type'] = orders['side']
        deposits = self.get_deposit_history(date_from, date_to, market)
        deposits['type'] = 'DEPOSIT'
        withdrawals = self.get_withdrawal_history(date_from, date_to, market)
        withdrawals['type'] = 'WITHDRAWAL'
        first_event = pd.DataFrame([{'time': 0, 'type': 'FIRST'}]) # need at least one record
        historic = pd.concat([orders, deposits, withdrawals, first_event]).sort_values(by='time', ascending=False)
        # initial balance
        balances = SnapshotAccountDetails.objects.filter(snapshot=snap)
        balances = {bal.asset : float(bal.amount) for bal in balances}
        # get all exchanges to track
        assets_to_track = set(balances.keys())
        for _, event in historic.iterrows():
            if pd.notna(event['asset']):
                assets_to_track = assets_to_track.union(set([event['asset']]))
            if pd.notna(event['base']):
                assets_to_track = assets_to_track.union(set([event['base']]))
        prices = pd.DataFrame(columns=['open_time', 'open_price', 'asset', 'base', 'symbol'])
        for asset in assets_to_track:
            # get price
            prices = prices.append(market.get_price_history(asset, 'USDT', date_from, date_to, interval), ignore_index=True)
            # initialize empty balance
            if asset not in balances.keys():
                balances[asset] = 0.0
        # walk through history backwards
        stats = pd.DataFrame(market.timestamp_range(date_from, date_to, interval), columns=['time'])
        stats['balance'] = 0.0
        stats = stats.set_index('time')

        event_id = 0
        old_event_time = market.to_timestamp(date_to)
        while event_id < len(historic):
            new_event = historic.iloc[event_id]
            new_event_time = new_event['time']
            for asset, amount in balances.items():
                if amount > 0.0:
                    asset_hist = prices[(prices['asset'] == asset) & (prices['open_time'].between(new_event_time, old_event_time))]
                    asset_hist['balance'] = asset_hist['open_price'] * amount
                    asset_hist = asset_hist[['open_time', 'balance']].set_index('open_time')
                    stats = stats.add(asset_hist, fill_value=0.0)
            # update balances, backwards in time
            if new_event['type'] == 'BUY':
                balances[new_event['asset']] -= new_event['amount']
                balances[new_event['base']] += (new_event['amount'] * new_event['price'])
            elif new_event['type'] == 'SELL':
                balances[new_event['asset']] += new_event['amount']
                balances[new_event['base']] -= (new_event['amount'] * new_event['price'])
            elif new_event['type'] == 'DEPOSIT':
                balances[new_event['asset']] -= new_event['amount']
            elif new_event['type'] == 'WITHDRAWAL':
                balances[new_event['asset']] += new_event['amount']

            old_event_time = new_event_time
            event_id += 1
        
        # get stats history
        stats = stats.reset_index().rename(columns={'index': 'time'})
        prices = prices.sort_values('open_time').astype({'open_time': int})
        # add deposits to pnl computations
        deposits = deposits.rename(columns={'time': 'deposit_time'}).sort_values('deposit_time').astype({'deposit_time': int})
        deposits = pd.merge_asof(deposits, prices, left_on='deposit_time', right_on='open_time', by='asset')
        deposits['deposit'] = deposits['amount'] * deposits['open_price']
        stats = stats.merge(deposits, how='left', left_on='time', right_on='open_time')
        stats = stats[['time', 'balance', 'deposit']]
        # add withdrawals to pnl computations
        withdrawals = withdrawals.rename(columns={'time': 'withdrawal_time'}).sort_values('withdrawal_time').astype({'withdrawal_time': int})
        withdrawals = pd.merge_asof(withdrawals, prices, left_on='withdrawal_time', right_on='open_time', by='asset')
        withdrawals['withdrawal'] = withdrawals['amount'] * withdrawals['open_price']
        stats = stats.merge(withdrawals, how='left', left_on='time', right_on='open_time')
        stats = stats[['time', 'balance', 'deposit', 'withdrawal']]
        # compute PnL
        stats['balance_open'] = stats['balance'].shift(1)
        stats['deposit_open'] = stats['deposit'].shift(1).fillna(0)
        stats['withdrawal_open'] = stats['withdrawal'].shift(1).fillna(0)
        stats['pnl'] = stats['balance'] - stats['balance_open'] - stats['deposit_open'] + stats['withdrawal_open']

        return stats, balances


    def set_balance_history(self, date_from, snap, market, interval='1h'):
        stats, balances = self.get_balance_history(date_from, snap, market, interval)
        stats = stats.where(pd.notnull(stats), None) # replace nan by None
        stats = stats.sort_values('time').reset_index()
        for i, stat in stats.iterrows():
            past_snap = SnapshotAccount(account=self.ta, 
                                   balance_btc=None, 
                                   balance_usdt=stat['balance'], 
                                   pnl_btc=None, 
                                   pnl_usdt=stat['pnl'], 
                                   created_at=market.to_datetime(stat['time']),
                                   updated_at=market.to_datetime(stat['time'])
                                   )
            past_snap.save()
            if i == 0:
                # save older snap details for potential more backward loading
                for asset, amount in balances.items():
                    if amount > 0.0:
                        details = SnapshotAccountDetails(snapshot=past_snap, asset=asset, amount=amount)
                        details.save()
            if i == len(stats) - 1:
                # update pnl of snap to avoid NaN
                snap.pnl_usdt = float(snap.balance_usdt) - stat['balance']
                snap.save()

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
