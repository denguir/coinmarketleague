from datetime import date, datetime
from Market import Market
from TradingClient import TradingClient
from traderboard.models import TradingAccount
from utils import to_series
from multipledispatch import dispatch
import numpy as np
import pandas as pd


class Trader(object):
    '''Class for every user-level aggregated functions that could be designed.'''
    def __init__(self, user, markets=None):
        self.user = user
        self.tas = TradingAccount.objects.filter(user=user)
        self.markets = self.load_markets(markets)
        self.tcs = [(TradingClient.trading_from(ta), self.markets[ta.platform]) for ta in self.tas]

    def load_markets(self, markets):
        if markets:
            return markets
        else:
            mkt = {}
            for ta in self.tas:
                if ta.platform not in mkt.keys():
                    mkt[ta.platform] = Market.trading_from(ta.platform)
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
        balances = {asset: amount for asset, amount in balances.items() if amount > 1e-8}
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
            balances = {asset: round(value*100/total, 2) for asset, value in balances.items() if value > 1e-8}
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

    def get_daily_balances(self, date_from, date_to, base='USDT'):
        '''Returns a historical balance time series aggregated by day'''
        balance_hist = pd.DataFrame(columns=['day', 'balance'])
        for tc, _ in self.tcs:
            tc_bal = tc.get_daily_balances(date_from, date_to, base)
            balance_hist = balance_hist.append(tc_bal)
        balance_hist = balance_hist.groupby('day')['balance'].sum()\
                                   .reset_index().sort_values('day')
        return balance_hist

    def get_daily_PnL(self, date_from, date_to, base='USDT'):
        '''Returns a historical PnL time series aggregated by day'''
        pnl_hist = pd.DataFrame(columns=['day', 'pnl'])
        for tc, _ in self.tcs:
            tc_pnl = tc.get_daily_PnL(date_from, date_to, base)
            pnl_hist = pnl_hist.append(tc_pnl)
        pnl_hist = pnl_hist.groupby('day')['pnl'].sum()\
                           .reset_index().sort_values('day')
        return pnl_hist

    def get_daily_relative_PnL(self, date_from, date_to, base='USDT'):
        pnl_hist = self.get_daily_PnL(date_from, date_to, base)
        balance_hist = self.get_daily_balances(date_from, date_to, base)
        rel_pnl_hist = pnl_hist.merge(balance_hist, 'inner', on='day')
        rel_pnl_hist['balance_open'] = rel_pnl_hist['balance'].shift(1)
        rel_pnl_hist['pnl_rel'] = rel_pnl_hist['pnl'] / rel_pnl_hist['balance_open']
        rel_pnl_hist = rel_pnl_hist.fillna({'pnl_rel': 0.0})
        return rel_pnl_hist

    def get_daily_cumulative_PnL(self, date_from, date_to, base='USDT'):
        '''Compute cumulative PnL for day_to w.r.t date_from, using the formula:
        cumPnL(t-n, t) = sum(dailyPnL(k) | k = t-n+1 -> t)'''
        daily_pnl = self.get_daily_PnL(date_from, date_to, base)
        daily_pnl['cum_pnl'] = daily_pnl['pnl'].cumsum()
        return daily_pnl

    def get_daily_cumulative_relative_PnL(self, date_from, date_to, base='USDT'):
        '''Compute cumulative relative PnL for date_to w.r.t date_from, using the formula:
        cumPnLPercent(t-n, t) = 100 * prod(1 + dailyPnLPercent(k) | k = t-n+1 -> t) - 100'''
        daily_pnl = self.get_daily_relative_PnL(date_from, date_to, base)
        daily_pnl['cum_pnl_perc'] = np.around(100 * np.cumprod(1.0 + daily_pnl['pnl_rel']) - 100, 2)
        return daily_pnl
    
    def get_order_history(self, date_from, date_to):
        order_hist = pd.DataFrame(columns=['created_at', 'symbol', 'amount', 'price', 'side'])
        for tc, _ in self.tcs:
            tc_order = tc.get_order_history(date_from, date_to)
            order_hist = order_hist.append(tc_order)
        return order_hist

    def get_transaction_history(self, date_from, date_to):
        trans_hist = pd.DataFrame(columns=['created_at', 'asset', 'amount', 'side'])
        for tc, _ in self.tcs:
            tc_trans = tc.get_transaction_history(date_from, date_to)
            trans_hist = trans_hist.append(tc_trans)
        return trans_hist

    def get_profile(self, date_from, date_to, base='USDT', overview=True):
        '''Process all metrics displayed in user's profile'''
        # TODO:
        # use dispatch to overload fct with df as param to speed up computation
        profile = {'user': self.user, 'currency': base}
        # get PnL aggregated history
        cum_pnl_hist = self.get_daily_cumulative_relative_PnL(date_from, date_to, base)
        cum_pnl_hist = {'labels': cum_pnl_hist['day'].apply(lambda x: x.strftime('%d %b')).tolist(),
                        'data': cum_pnl_hist['cum_pnl_perc'].tolist()}
        profile['cum_pnl_hist'] = cum_pnl_hist
        # get balance percentage
        balance_percentage = to_series(self.get_relative_balances(base))
        profile['balance_percentage'] = balance_percentage

        # get order history
        trades_hist = [{'time': datetime.now().strftime('%d %b %H:%M:%S'), 'symbol': 'ETHUSDT', 'amount': 3, 'side': 'BUY'}]
        profile['trades_hist'] = trades_hist

        profile['overview'] = overview
        # get private information
        if not overview:
            # get balance aggregated history
            balance_hist = self.get_daily_balances(date_from, date_to, base)
            balance_hist = {'labels': balance_hist['day'].apply(lambda x: x.strftime('%d %b')).tolist(),
                            'data': balance_hist['balance'].tolist()}
            profile['balance_hist'] = balance_hist
            # get balance info now
            balance = round(self.get_balances_value(base), 2)
            profile['balance'] = balance
            # get daily pnl
            daily_pnl_hist = self.get_daily_PnL(date_from, date_to, base)
            daily_pnl_hist = {'labels': daily_pnl_hist['day'].apply(lambda x: x.strftime('%d %b')).tolist(),
                              'data': daily_pnl_hist['pnl'].tolist()}
            profile['daily_pnl_hist'] = daily_pnl_hist
        return profile

