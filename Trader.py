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

    def get_relative_PnL(self, date_from, now, margin, base='USDT'):

        def get_closest_to_dt(qs, dt):
            greater = qs.filter(created_at__gte=dt).order_by("created_at").first()
            less = qs.filter(created_at__lte=dt).order_by("-created_at").first()
            
            if greater and less:
                return greater if abs(greater.created_at - dt) < abs(less.created_at - dt) else less
            else:
                return greater or less

        pnl = 0.0
        bal_from = 0.0
        for tc, market in self.tcs:
            snaps = SnapshotAccount.objects.filter(account=tc.ta)
            snap = get_closest_to_dt(snaps, date_from)
            if snap is not None:
                if abs(snap.created_at - date_from) < margin:
                    pnl += tc.get_PnL(snap, now, market, base)
                    if base == 'BTC':
                        bal_from += float(snap.balance_btc)
                    else:
                        bal_from += float(snap.balance_usdt)
        if bal_from > 0:
            pnl_rel = pnl / bal_from
        else:
            pnl_rel = None
        return pnl_rel

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
        return order_hist.sort_values('created_at', ascending=False)

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
        profile = {'trader': self.user, 'currency': base}
        # get PnL aggregated history
        cum_pnl_hist = self.get_daily_cumulative_relative_PnL(date_from, date_to, base)
        cum_pnl_hist = {'labels': cum_pnl_hist['day'].apply(lambda x: x.strftime('%d %b')).tolist(),
                        'data': cum_pnl_hist['cum_pnl_perc'].tolist()}
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

            # get transaction history
            # trans_hist = self.get_transaction_history(date_from, date_to)
            # trans_hist['time'] = trans_hist['created_at'].apply(lambda x: x.strftime('%d %b %Y %H:%M:%S'))
            # trans_hist = trans_hist.to_dict('records')
            # profile['trans_hist'] = trans_hist
        return profile

