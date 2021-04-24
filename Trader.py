from datetime import date
from Market import Market
from TradingClient import TradingClient
from traderboard.models import TradingAccount, SnapshotProfile
from django.db.models.functions import TruncDay
from collections import OrderedDict
from django.db.models import Avg
from utils import to_series, to_time_series
import numpy as np


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
        '''returns a historical balance time series aggregated by day'''
        snaps = SnapshotProfile.objects.filter(profile=self.user.profile)\
                                       .annotate(day=TruncDay('created_at'))\
                                       .filter(day__range=[date_from, date_to])\
                                       .values('day')
        balance_hist = OrderedDict()
        data = []
        if base == 'USDT':
            data = snaps.annotate(avg_bal=Avg('balance_usdt')).order_by('day')

        elif base == 'BTC':
            data = snaps.annotate(avg_bal=Avg('balance_btc')).order_by('day')

        for snap in data:
            balance_hist[snap['day']] = float(snap['avg_bal'])
        return balance_hist

    
    def get_PnL(self, snap, now, base='USDT'):
        deposits = self.get_deposits_value(snap.created_at, now, base)
        withdrawals = self.get_withdrawals_value(snap.created_at, now, base)
        balance_now = self.get_balances_value(base)

        if base == 'USDT':
            balance_from = float(snap.balance_usdt)
        elif base == 'BTC':
            balance_from = float(snap.balance_btc)

        pnl = round((balance_now - deposits + withdrawals - balance_from)*100 / balance_from, 2)
        return pnl


    def get_daily_PnL(self, date_from, date_to, base='USDT'):
        '''Compute PnL for each day w.r.t previous day, using the formula:
        PnL(t) = bal(t) - [bal(t-1) + dep(t-1, t) - wit(t-1, t)]'''
        pnl_hist = OrderedDict()
        balance_hist = self.get_daily_balances(date_from, date_to, base)
        days = list(balance_hist.keys())
        deposit_hist = self.get_daily_deposits_value(date_from, date_to, base)
        withdrawal_hist = self.get_daily_withdrawals_value(date_from, date_to, base)
        
        for t in range(len(days)):
            if t == 0:
                pnl_hist[days[t]] = 0.0
            else:
                dep = deposit_hist.get(days[t], 0.0)
                wit = withdrawal_hist.get(days[t], 0.0)
                pnl_hist[days[t]] = balance_hist[days[t]] - balance_hist[days[t-1]] - dep + wit
        return pnl_hist


    def get_daily_relative_PnL(self, date_from, date_to, base='USDT'):
        '''Compute relative PnL for each day w.r.t previous day, using formula:
        PnLPerc(t) = bal(t) - bal(t-1) - dep(t-1, t) + wit(t-1, t) / bal(t-1)'''
        pnl_hist = OrderedDict()
        balance_hist = self.get_daily_balances(date_from, date_to, base)
        days = list(balance_hist.keys())
        deposit_hist = self.get_daily_deposits_value(date_from, date_to, base)
        withdrawal_hist = self.get_daily_withdrawals_value(date_from, date_to, base)

        for t in range(len(days)):
            if t == 0:
                pnl_hist[days[t]] = 0.0
            else:
                dep = deposit_hist.get(days[t], 0.0)
                wit = withdrawal_hist.get(days[t], 0.0)
                try:
                    pnl_hist[days[t]] = (balance_hist[days[t]] - balance_hist[days[t-1]] - dep + wit) / balance_hist[days[t-1]]
                except ZeroDivisionError:
                    pnl_hist[days[t]] = 0.0
        return pnl_hist


    def get_daily_cumulative_PnL(self, date_from, date_to, base='USDT'):
        '''Compute cumulative PnL for day_to w.r.t date_from, using the formula:
        cumPnL(t-n, t) = sum(dailyPnL(k) | k = t-n+1 -> t)'''
        daily_pnl = self.get_daily_PnL(date_from, date_to, base)
        days = daily_pnl.keys()
        cum_pnl = np.cumsum(list(daily_pnl.values()))
        return OrderedDict(zip(days, cum_pnl))


    def get_daily_cumulative_relative_PnL(self, date_from, date_to, base='USDT'):
        '''Compute cumulative relative PnL for date_to w.r.t date_from, using the formula:
        cumPnLPercent(t-n, t) = 100 * prod(1 + dailyPnLPercent(k) | k = t-n+1 -> t) - 100'''
        daily_pnl = self.get_daily_relative_PnL(date_from, date_to, base)
        days = daily_pnl.keys()
        cum_pnl = np.around(100 * np.cumprod(1.0 + np.array(list(daily_pnl.values()))) - 100, 2)
        return OrderedDict(zip(days, cum_pnl))


    def get_profile(self, date_from, date_to, base='USDT', overview=True):
        '''Process all metrics displayed in user's profile'''
        profile = {'user': self.user, 'currency': base}
        # get PnL aggregated history
        cum_pnl_hist = to_time_series(self.get_daily_cumulative_relative_PnL(date_from, date_to, base))
        profile['cum_pnl_hist'] = cum_pnl_hist
        # get balance percentage
        balance_percentage = to_series(self.get_relative_balances(base))
        profile['balance_percentage'] = balance_percentage

        profile['overview'] = overview
        # get private information
        if not overview:
            # get balance aggregated history
            balance_hist = to_time_series(self.get_daily_balances(date_from, date_to, base))
            profile['balance_hist'] = balance_hist
            # get balance info now
            balance = round(self.get_balances_value(base), 2)
            profile['balance'] = balance
            # get daily pnl
            daily_pnl_hist = to_time_series(self.get_daily_PnL(date_from, date_to, base))
            profile['daily_pnl_hist'] = daily_pnl_hist
        return profile

