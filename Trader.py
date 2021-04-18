from datetime import date, datetime
from operator import le
from TradingClient import TradingClient
from traderboard.models import TradingAccount, SnapshotProfile
from django.db.models.functions import TruncMonth, TruncDay
from collections import OrderedDict
from django.db.models import Avg
import numpy as np


class Trader(object):
    '''class for every user-level aggregated functions that could be designed.
        This eases future development as well as clean up main script'''
    def __init__(self, user, markets):
        self.user = user
        self.markets = markets # dict of markets
        self.tas = TradingAccount.objects.filter(user=user).iterator()
        self.tcs = [(TradingClient.trading_from(ta), self.markets[ta.platform]) for ta in self.tas]
    

    def get_balances(self):
        balances = {}
        for tc, _ in self.tcs:
            tc_bal = tc.get_balances()
            for asset, amount in tc_bal.items():
                if asset in balances.keys():
                    balances[asset] += amount
                else:
                    balances[asset] = amount
        balances = {asset: amount for asset, amount in balances.items() if amount > 1e-8}
        return balances
    

    def get_relative_balances(self, base='USDT'):
        balances = {}
        for tc, market in self.tcs:
            tc_bal = tc.get_balances()
            for asset, amount in tc_bal.items():
                val = tc.get_asset_value(asset, market, base)
                if asset in balances.keys():
                    balances[asset] += (amount * val)
                else:
                    balances[asset] = amount * val
        total = sum(balances.values())
        if total > 0.0:
            balances = {asset: round(amount*100/total, 2) for asset, amount in balances.items() if amount > 1e-8}
        else:
            balances = {}
        return balances


    def get_balances_value(self, base='USDT'):
        return sum(tc.get_balances_value(market, base) for tc, market in self.tcs)


    def get_deposits_value(self, date_from, date_to, base='USDT'):
        return sum(tc.get_deposits_value(date_from, date_to, market, base) for tc, market in self.tcs)


    def get_withdrawals_value(self, date_from, date_to, base='USDT'):
        return sum(tc.get_withdrawals_value(date_from, date_to, market, base) for tc, market in self.tcs)


    def get_historical_balances(self, date_from, date_to, base='USDT'):
        '''returns a historical balance time series aggregated by day'''
        snaps = SnapshotProfile.objects.filter(profile=self.user.profile)\
                                       .filter(created_at__range=[date_from, date_to])\
                                       .annotate(day=TruncDay('created_at'))\
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


    def get_historical_daily_PnL(self, date_from, date_to, base='USDT'):
        '''Compute PnL for each day w.r.t previous day, using the formula:
        PnL(t) = bal(t) - [bal(t-1) + dep(t-1, t) - wit(t-1, t)]'''
        balance_hist = self.get_historical_balances(date_from, date_to, base)
        pnl_hist = OrderedDict()
        if len(balance_hist) > 1:
            days = list(balance_hist.keys()) # make sure no wholes in days consecutive
            deposit_hist = [self.get_deposits_value(days[t], days[t+1], base) for t in range(len(days) - 1)]
            withdrawal_hist = [self.get_withdrawals_value(days[t], days[t+1], base) for t in range(len(days) - 1)]
            for t in range(1, len(days)):
                pnl_hist[days[t]] = balance_hist[days[t]] - balance_hist[days[t-1]] - deposit_hist[t-1] + withdrawal_hist[t-1]
        return pnl_hist


    def get_historical_daily_relative_PnL(self, date_from, date_to, base='USDT'):
        '''Compute relative PnL for each day w.r.t previous day, using formula:
        PnLPerc(t) = bal(t) - bal(t-1) - dep(t-1, t) + wit(t-1, t) / bal(t-1)'''
        balance_hist = self.get_historical_balances(date_from, date_to, base)
        pnl_hist = OrderedDict()
        if len(balance_hist) > 1:
            days = list(balance_hist.keys()) # make sure no wholes in days consecutive
            deposit_hist = [self.get_deposits_value(days[t], days[t+1], base) for t in range(len(days) - 1)]
            withdrawal_hist = [self.get_withdrawals_value(days[t], days[t+1], base) for t in range(len(days) - 1)]
            for t in range(1, len(days)):
                pnl_hist[days[t]] = \
                    (balance_hist[days[t]] - balance_hist[days[t-1]] - deposit_hist[t-1] + withdrawal_hist[t-1]) / balance_hist[days[t-1]]
        return pnl_hist


    def get_historical_cumulative_PnL(self, date_from, date_to, base='USDT'):
        '''Compute cumulative PnL for day_to w.r.t date_from, using the formula:
        cumPnL(t-n, t) = sum(dailyPnL(k) | k = t-n+1 -> t)'''
        daily_pnl = self.get_historical_daily_PnL(date_from, date_to, base)
        days = daily_pnl.keys()
        cum_pnl = np.cumsum(list(daily_pnl.values()))
        return OrderedDict(zip(days, cum_pnl))


    def get_historical_cumulative_relative_PnL(self, date_from, date_to, base='USDT'):
        '''Compute cumulative relative PnL for date_to w.r.t date_from, using the formula:
        cumPnLPercent(t-n, t) = 100 * prod(1 + dailyPnLPercent(k) | k = t-n+1 -> t) - 100'''
        daily_pnl = self.get_historical_daily_relative_PnL(date_from, date_to, base)
        days = daily_pnl.keys()
        cum_pnl = np.around(100 * np.cumprod(1.0 + np.array(list(daily_pnl.values()))) - 100, 2)
        return OrderedDict(zip(days, cum_pnl))
