from TradingClient import TradingClient
from traderboard.models import TradingAccount
from Market import Market

class Trader(object):

    def __init__(self, user, markets):
        self.user = user
        self.markets = markets # dict of markets
        self.tas = TradingAccount.objects.filter(user=user).iterator()
        self.tcs = [(TradingClient.trading_from(ta), self.markets[ta.platform]) for ta in self.tas]
    
    # every user-level aggregated functions that could be designed
    # will ease the future development as well as clean update_board script

    def get_balances(self):
        balances = {}
        for tc, _ in self.tcs:
            tc_bal = tc.get_balances()
            for asset, amount in tc_bal.items():
                if asset in balances.keys():
                    balances[asset] += amount
                else:
                    balances[asset] = amount
        return balances
    
    def get_relative_balances(self, base='USDT'):
        balances = {}
        for tc, market in self.tcs:
            tc_bal = tc.get_balances()
            for asset, amount in tc_bal.items():
                val = tc.get_asset_value(asset, tc_bal, market, base)
                if asset in balances.keys():
                    balances[asset] += (amount * val)
                else:
                    balances[asset] = amount * val
        total = sum(balances.values())
        if total > 0.0:
            balances = {asset: amount/total for asset, amount in balances if amount > 0.0}
        else:
            balances = {}
        return balances

    def get_balances_value(self, base='USDT'):
        return sum(tc.get_balances_value(market, base) for tc, market in self.tcs)

    def get_deposits_values(self, date_from, date_to, base='USDT'):
        return sum(tc.get_deposits_value(date_from, date_to, market, base) for tc, market in self.tcs)

    def get_withdrawals_value(self, date_from, date_to, base='USDT'):
        return sum(tc.get_withdrawals_value(date_from, date_to, market, base) for tc, market in self.tcs)

    def get_PnL(self, date_from, date_to, base='USDT'):
        deposits = self.get_deposits_value(snap_from.created_at, snap_to.created_at, base)
        withdrawals = self.get_withdrawals_value(snap_from.created_at, snap_to.created_at, base)
        pnl = (balance_to - deposits + withdrawals - balance_from) / balance_from
        return pnl