import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

from Market import Market
from TradingClient import TradingClient
from datetime import datetime, timedelta, timezone
from django.contrib.auth.models import User
from Trader import Trader
from traderboard.tasks import update_profile
from traderboard.models import SnapshotAccount, SnapshotAccountDetails, TradingAccount, AccountTrades, AccountTransactions
import pandas as pd


__PLATFORMS__ = ['Binance']


date_to = datetime.now(timezone.utc) - timedelta(days=30)
date_from = date_to - timedelta(days=29)
user = User.objects.get(username='Vador')
ta = TradingAccount.objects.get(user=user)
tc = TradingClient.trading_from(ta)

market = Market.trading_from('Binance')
start = market.to_timestamp(date_from)
end = market.to_timestamp(date_to)

# get balance history
hist = tc.client.get_account_snapshot(type='SPOT', startTime=start, endTime=end)['snapshotVos']
snapshots = pd.DataFrame([{'asset': bal['asset'], 
                            'amount': float(bal['free']) + float(bal['locked']), 
                            'timestamp': snap['updateTime'] + 999}
                            for snap in hist for bal in snap['data']['balances']])

deposits = tc.get_deposit_history(date_from, date_to, market).sort_values('time')
withdrawals = tc.get_withdrawal_history(date_from, date_to, market).sort_values('time')

assets_to_track = set(snapshots['asset']).union(set(deposits['asset'])).union(set(withdrawals['asset']))

btc_usdt_prices = market.get_price_history('BTC', 'USDT', date_from, date_to, '1d')
prices = pd.DataFrame(columns=['open_time', 'open_price', 'close_time', 'close_price', 'asset', 'base', 'symbol'])
for asset in assets_to_track:
    prices = prices.append(market.get_price_history(asset, 'BTC', date_from, date_to, '1d'))

# get prices in usdt
prices = prices.merge(btc_usdt_prices, on=['open_time', 'close_time'], suffixes=("_btc", "_usdt"))
prices['open_price_usdt'] = prices['open_price_btc'] * prices['open_price_usdt']
prices['close_price_usdt'] = prices['close_price_btc'] * prices['close_price_usdt']
prices['open_time'] = prices['open_time'].astype(int)
prices['close_time'] = prices['close_time'].astype(int)

# compute balances
stats = snapshots.merge(prices, left_on=['asset', 'timestamp'], right_on=['asset_btc', 'close_time'])
stats['open_balance_btc'] = stats['amount'] * stats['open_price_btc']
stats['close_balance_btc'] = stats['amount'] * stats['close_price_btc']
stats['open_balance_usdt'] = stats['amount'] * stats['open_price_usdt']
stats['close_balance_usdt'] = stats['amount'] * stats['close_price_usdt']

# compute pnl
stats['pnl_btc'] = stats['close_balance_btc'] - stats['open_balance_btc']
stats['pnl_usdt'] = stats['close_balance_usdt'] - stats['open_balance_usdt']

# include deposits and withdrawals in pnl computation
deposits = deposits.rename(columns={'amount': 'dep_amount', 'time': 'dep_time'})
withdrawals = withdrawals.rename(columns={'amount': 'wit_amount', 'time': 'wit_time'})

if not deposits.empty:
    deposits = pd.merge_asof(deposits, stats, left_on='dep_time', right_on='open_time', by='asset')
    deposits['deposits_btc'] = deposits['dep_amount'] * deposits['close_price_btc']
    deposits['deposits_usdt'] = deposits['dep_amount'] * deposits['close_price_usdt']
    deposits = deposits[['open_time', 'close_time', 'dep_time', 'dep_amount', 'asset', 'deposits_btc', 'deposits_usdt']]

    stats = stats.merge(deposits, how='left', on=['open_time', 'close_time', 'asset'])
    stats['pnl_btc'] = stats['pnl_btc'].sub(deposits['deposits_btc'], fill_value=0.0)
    stats['pnl_usdt'] = stats['pnl_usdt'].sub(deposits['deposits_usdt'], fill_value=0.0)


if not withdrawals.empty:
    withdrawals = pd.merge_asof(withdrawals, stats, left_on='wit_time', right_on='open_time', by='asset')
    withdrawals['withdrawals_btc'] = withdrawals['wit_amount'] * withdrawals['close_price_btc']
    withdrawals['withdrawals_usdt'] = withdrawals['wit_amount'] * withdrawals['close_price_usdt']
    withdrawals = withdrawals[['open_time', 'close_time', 'wit_time', 'wit_amount', 'asset', 'withdrawals_btc', 'withdrawals_usdt']]

    stats = stats.merge(withdrawals, how='left', on=['open_time', 'close_time', 'asset'])
    stats['pnl_btc'] = stats['pnl_btc'].add(withdrawals['withdrawals_btc'], fill_value=0.0)
    stats['pnl_usdt'] = stats['pnl_usdt'].add(withdrawals['withdrawals_usdt'], fill_value=0.0)

stats = stats.groupby('open_time')

for ts, stat in stats:
    print(market.to_datetime(ts))
    print(stat['close_balance_btc'].sum())