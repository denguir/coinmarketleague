from Market import Market
from TradingClient import TradingClient
from traderboard.models import TradingAccount, SnapshotAccount
import numpy as np
import pandas as pd
import time

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

    def get_daily_deposits_value(self, date_from, date_to, base='USDT'):
        deposits = {}
        for tc, market in self.tcs:
            tc_dep = tc.get_daily_deposits_value(date_from, date_to, market, base)
            for date, value in tc_dep.items():
                if date in deposits.keys():
                    deposits[date] += value
                else:
                    deposits[date] = value
        return deposits

    def get_withdrawals_value(self, date_from, date_to, base='USDT'):
        return sum(tc.get_withdrawals_value(date_from, date_to, market, base) for tc, market in self.tcs)

    def get_daily_withdrawals_value(self, date_from, date_to, base='USDT'):
        withdrawals = {}
        for tc, market in self.tcs:
            tc_wit = tc.get_daily_withdrawals_value(date_from, date_to, market, base)
            for date, value in tc_wit.items():
                if date in withdrawals.keys():
                    withdrawals[date] += value
                else:
                    withdrawals[date] = value
        return withdrawals

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
        snaps['balance_open'] = snaps['balance'].shift(1)
        snaps['pnl_rel'] = snaps['pnl'] / snaps['balance_open']
        snaps['cum_pnl'] = snaps['pnl'].cumsum()
        snaps['cum_pnl_rel'] = np.around(100 * snaps['cum_pnl'] / snaps.iloc[0].balance, 2)
        return snaps

    def get_aggregated_stats(self, date_from, date_to, freq, base='USDT'):
        '''Aggregate stats by freq, day: D, hour: H,
           see: https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#offset-aliases
        '''
        snaps = self.get_snapshot_history(date_from, date_to, base)
        snaps['balance_open'] = snaps['balance'].shift(1)
        snaps = snaps.groupby(pd.Grouper(key='created_at',freq=freq))\
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
        return snaps
    
    def get_order_history(self, date_from, date_to):
        order_hist = pd.DataFrame(columns=['created_at', 'symbol', 'amount', 'price', 'side'])
        for tc, _ in self.tcs:
            tc_order = tc.get_order_history(date_from, date_to)
            order_hist = order_hist.append(tc_order)
        return order_hist.sort_values('created_at', ascending=False)

    def get_transaction_history(self, date_from, date_to):
        trans_hist = pd.DataFrame(columns=['created_at', 'asset', 'amount', 'side'])
        for tc, market in self.tcs:
            tc_trans = tc.get_transaction_history(date_from, date_to, market)
            trans_hist = trans_hist.append(tc_trans)
        return trans_hist

    def get_profile(self, date_from, date_to, base='USDT', overview=True):
        '''Process all metrics displayed in user's profile'''
        profile = {'trader': self.user, 'currency': base}

        # collect daily stats and interpolate missing values
        stats = self.get_aggregated_stats(date_from, date_to, freq='D', base=base)
<<<<<<< HEAD
=======
        print(stats)
>>>>>>> master
        # get PnL aggregated history
        cum_pnl_hist = {'labels': stats['created_at'].apply(
                                    lambda x: x.to_pydatetime().strftime('%d %b')).tolist(),
                        'data': stats['cum_pnl_rel'].tolist()}
        profile['cum_pnl_hist'] = cum_pnl_hist

        # get balance percentage
        balance_percentage = self.get_relative_balances(base)
        balance_percentage = {'labels': [key for key in balance_percentage.keys()], 
                              'data': [value for value in balance_percentage.values()]}
        profile['balance_percentage'] = balance_percentage

        # get order history
        # trades_hist = self.get_order_history(date_from, date_to)
        # trades_hist['time'] = trades_hist['created_at'].apply(lambda x: x.strftime('%d %b %Y %H:%M:%S'))
        # trades_hist = trades_hist.to_dict('records')
        # profile['trades_hist'] = trades_hist

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
            # trans_hist = self.get_transaction_history(date_from, date_to)
            # trans_hist['time'] = trans_hist['created_at'].apply(lambda x: x.strftime('%d %b %Y %H:%M:%S'))
            # trans_hist = trans_hist.to_dict('records')
            # profile['trans_hist'] = trans_hist
        return profile