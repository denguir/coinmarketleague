from Trader import Trader
from traderboard.models import TradingAccount
from utils import to_series
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async


@sync_to_async
def get_trader(pk):
    user = User.objects.get(pk=pk)
    return Trader(user)


@sync_to_async
def get_daily_cumulative_relative_PnL(pk, date_from, date_to, base):
    user = User.objects.get(pk=pk)
    trader = Trader(user)
    cum_pnl_hist = trader.get_daily_cumulative_relative_PnL(date_from, date_to, base)
    cum_pnl_hist = {'labels': cum_pnl_hist['day'].apply(lambda x: x.strftime('%d %b')).tolist(),
                    'data': cum_pnl_hist['cum_pnl_perc'].tolist()}
    return cum_pnl_hist


@sync_to_async
def get_relative_balances(pk, base):
    user = User.objects.get(pk=pk)
    trader = Trader(user)
    balance_percentage = to_series(trader.get_relative_balances(base))
    return balance_percentage


@sync_to_async
def get_daily_balances(pk, date_from, date_to, base):
    user = User.objects.get(pk=pk)
    trader = Trader(user)
    balance_hist = trader.get_daily_balances(date_from, date_to, base)
    balance_hist = {'labels': balance_hist['day'].apply(lambda x: x.strftime('%d %b')).tolist(),
                    'data': balance_hist['balance'].tolist()}
    return balance_hist


@sync_to_async
def get_balances_value(pk, base):
    user = User.objects.get(pk=pk)
    trader = Trader(user)
    balance = round(trader.get_balances_value(base), 2)
    return balance


@sync_to_async
def get_daily_PnL(pk, date_from, date_to, base):
    user = User.objects.get(pk=pk)
    trader = Trader(user)
    daily_pnl_hist = trader.get_daily_PnL(date_from, date_to, base)
    daily_pnl_hist = {'labels': daily_pnl_hist['day'].apply(lambda x: x.strftime('%d %b')).tolist(),
                      'data': daily_pnl_hist['pnl'].tolist()}
    return daily_pnl_hist

