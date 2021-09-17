from Market import Market
from TradingClient import TradingClient
from traderboard.models import TradingAccount, SnapshotAccount
import numpy as np
import pandas as pd


class Trader(object):
    '''Class for every user-level aggregated functions that could be designed.'''
    def __init__(self, user, markets=None):
        self.user = user
        self.tas = TradingAccount.objects.filter(user=user)
        self.markets = self.load_markets(markets)
        self.tcs = [(TradingClient.connect(ta), self.markets[ta.platform]) for ta in self.tas]

    def load_markets(self, markets):
        if markets:
            return markets
        else:
            mkt = {}
            for ta in self.tas:
                if ta.platform not in mkt.keys():
                    mkt[ta.platform] = Market.connect(ta.platform)
            return mkt

    def get_balances(self):
        balances = {}
        for tc, _ in self.tcs:
            tc_bal = tc.get_balances()
            tc_bal = {asset: amount for asset, amount in zip(tc_bal['asset'], tc_bal['amount'])}
            for asset, amount in tc_bal.items():
                if asset in balances.keys():
                    balances[asset] += amount
                else:
                    balances[asset] = amount
        balances = {asset: amount for asset, amount in balances.items()}
        return balances
    
    def get_relative_balances(self, base='USDT'):
        total = 0.0
        balances = {}
        for tc, market in self.tcs:
            tc_bal = tc.get_balances()
            value_table = tc.get_value_table(tc_bal, market, base)
            total += sum(value_table['value'])
            tc_value = value_table.groupby('asset')['value'].sum().to_dict()
            for asset, value in tc_value.items():
                if asset in balances.keys():
                    balances[asset] += value
                else:
                    balances[asset] = value
        if total > 0.0:
            balances = {asset: round(value*100/total, 2) for asset, value in balances.items()}
            balances = {asset: percentage for asset, percentage in balances.items() if percentage >= 0.1}
        return balances

    def get_balances_value(self, base='USDT'):
        return sum(tc.get_balances_value(market, base) for tc, market in self.tcs)

    def get_deposits_value(self, date_from, date_to, base='USDT'):
        return sum(tc.get_deposits_value(date_from, date_to, market, base) for tc, market in self.tcs)

    def get_withdrawals_value(self, date_from, date_to, base='USDT'):
        return sum(tc.get_withdrawals_value(date_from, date_to, market, base) for tc, market in self.tcs)

    def get_snapshot_history(self, date_from, date_to, base='USDT'):
        snaps = pd.DataFrame(columns=['created_at', 'pnl', 'balance'])
        for tc, _ in self.tcs:
            tc_snaps = tc.get_snapshot_history(date_from, date_to, base)
            snaps = snaps.append(tc_snaps)
        snaps = snaps.sort_values('created_at')
        if len(snaps) > 0:
            snaps.loc[0, 'pnl'] = 0 # first record becomes the reference
        return snaps

    def get_stats(self, date_from, date_to, base='USDT'):
        snaps = self.get_snapshot_history(date_from, date_to, base)
        if not snaps.empty:
            snaps['balance_open'] = snaps['balance'].shift(1)
            snaps['pnl_rel'] = snaps['pnl'] / snaps['balance_open']
            snaps['cum_pnl'] = snaps['pnl'].cumsum()
            snaps['cum_pnl_rel'] = np.around(100 * snaps['cum_pnl'] / snaps.iloc[0].balance, 2)
        else:
            snaps = pd.DataFrame(columns=['created_at', 'pnl', 'balance', 
                                          'balance_open', 'pnl_rel',
                                          'cum_pnl', 'cum_pnl_rel'])
        return snaps

    def get_aggregated_stats(self, date_from, date_to, freq, base='USDT'):
        '''Aggregate stats by freq, day: D, hour: H,
           see: https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#offset-aliases
        '''
        snaps = self.get_snapshot_history(date_from, date_to, base)
        if not snaps.empty:
            snaps['balance_open'] = snaps['balance'].shift(1)
            snaps = snaps.groupby(pd.Grouper(key='created_at', freq=freq))\
                         .agg({'pnl': 'sum',
                               'balance': 'last',
                               'balance_open': 'first'
                            })\
                        .reset_index()\
                        .sort_values('created_at')
            # remove nan introduced by groupby
            snaps = snaps[snaps['balance'].notna()]
            snaps['balance_open'] = snaps['balance_open'].fillna(snaps['balance'])
            snaps['pnl_rel'] = snaps['pnl'] / snaps['balance_open']
            snaps['cum_pnl'] = snaps['pnl'].cumsum()
            snaps['cum_pnl_rel'] = np.around(100 * snaps['cum_pnl'] / snaps.iloc[0].balance_open, 2)
        else:
            snaps = pd.DataFrame(columns=['created_at', 'pnl', 'balance', 
                                          'balance_open', 'pnl_rel',
                                          'cum_pnl', 'cum_pnl_rel'])
        return snaps

    def get_btc_stats(self, date_from, date_to, freq, base='USDT'):
        binance_market = self.markets['Binance']
        btc_stats = binance_market.get_price_history('BTC', base, date_from, date_to, freq)
        btc_stats['created_at'] = btc_stats['open_time'].apply(Market.to_datetime)
        btc_stats['pnl'] = btc_stats['close_price'] - btc_stats['open_price']
        btc_stats['pnl_rel'] = btc_stats['pnl'] / btc_stats['open_price']
        btc_stats['cum_pnl'] = btc_stats['pnl'].cumsum()
        btc_stats['cum_pnl_rel'] = np.around(100 * btc_stats['cum_pnl'] / btc_stats.iloc[0].close_price, 2)
        return btc_stats

    def get_transaction_history(self, date_from, date_to):
        trans = pd.DataFrame(columns=['created_at', 'asset', 'amount', 'side'])
        for tc, _ in self.tcs:
            tc_trans = tc.get_transaction_history(date_from, date_to)
            trans = trans.append(tc_trans)
        trans = trans.sort_values('created_at', ascending=False)
        return trans

    def get_trade_history(self, date_from, date_to):
        trades = pd.DataFrame(columns=['created_at', 'symbol', 'amount', 'price', 'side'])
        for tc, _ in self.tcs:
            tc_trades = tc.get_trade_history(date_from, date_to)
            trades = trades.append(tc_trades)
        trades = trades.sort_values('created_at', ascending=False)
        return trades

    def get_profile(self, date_from, date_to, base='USDT', overview=True):
        '''Process all metrics displayed in user's profile'''
        profile = {'trader': self.user, 'currency': base}

        # collect daily stats and interpolate missing values
        stats = self.get_aggregated_stats(date_from, date_to, freq='D', base=base)
        
        # compute BTC stats on same time window
        btc_stats = self.get_btc_stats(stats.created_at.min().to_pydatetime(), 
                                       stats.created_at.max().to_pydatetime(),
                                       freq='1d', 
                                       base=base)
        # get PnL aggregated history
        cum_pnl_hist = {'labels': stats['created_at'].apply(
                                    lambda x: x.to_pydatetime().strftime('%d %b')).tolist(),
                        'data': stats['cum_pnl_rel'].tolist(),
                        'btc_data': btc_stats['cum_pnl_rel'].tolist()}
        profile['cum_pnl_hist'] = cum_pnl_hist
    
        # get balance percentage
        balance_percentage = self.get_relative_balances(base)
        balance_percentage = {'labels': [key for key in balance_percentage.keys()], 
                              'data': [value for value in balance_percentage.values()]}
        profile['balance_percentage'] = balance_percentage

        # get trade history
        trades_hist = self.get_trade_history(date_from, date_to)
        trades_hist['time'] = trades_hist['created_at'].apply(lambda x: x.to_pydatetime().strftime('%d %b %Y %H:%M:%S (UTC)'))
        trades_hist['amount'] = trades_hist['amount'].apply(lambda x: x.normalize())
        trades_hist['price'] = trades_hist['price'].apply(lambda x: x.normalize())
        profile['trades_hist'] = trades_hist.to_dict('records')

        profile['overview'] = overview
        # get private information
        if not overview:
            # get balance aggregated history
            balance_hist = {'labels': stats['created_at'].apply(
                                        lambda x: x.to_pydatetime().strftime('%d %b')).tolist(),
                            'data': stats['balance'].tolist()}
            profile['balance_hist'] = balance_hist

            # get balance info now
            balance = round(self.get_balances_value(base), 2)
            profile['balance'] = balance

            # get daily pnl
            daily_pnl_hist = {'labels': stats['created_at'].apply(
                                            lambda x: x.to_pydatetime().strftime('%d %b')).tolist(),
                              'data': stats['pnl'].tolist()}
            profile['daily_pnl_hist'] = daily_pnl_hist

            # get transaction history
            trans_hist = self.get_transaction_history(date_from, date_to)
            trans_hist['time'] = trans_hist['created_at'].apply(lambda x: x.to_pydatetime().strftime('%d %b %Y %H:%M:%S (UTC)'))
            trans_hist['amount'] = trans_hist['amount'].apply(lambda x: x.normalize())
            profile['trans_hist'] = trans_hist.to_dict('records')

        return profile