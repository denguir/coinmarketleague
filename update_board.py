import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

from django.contrib.auth.models import User
from traderboard.models import TradingAccount, SnapshotAccount, SnapshotAccountDetails
from TradingClient import TradingClient
from Market import Market

__PLATFORMS__ = ['Binance']

def get_price_table():
    markets = [Market.trading_from(platform) for platform in __PLATFORMS__]
    prices = {m.platform : m.get_price_table() for m in markets}
    return prices


if __name__ == '__main__':
    tas = TradingAccount.objects.all()
    markets = get_price_table()
    for ta in tas:
        price_table = markets[ta.platform]
        tc = TradingClient.trading_from(ta)
        balance_details = tc.get_balances()
        balance_btc = tc.get_balances_value(price_table, 'BTC')
        balance_usdt = tc.get_balances_value(price_table, 'USDT')

        # save snapshot and details
        snap = SnapshotAccount(account=ta, balance_btc=balance_btc, balance_usdt=balance_usdt)
        snap.save()
        for asset, amount in balance_details.items():
            details = SnapshotAccountDetails(snapshot=snap, asset=asset, amount=amount)
            details.save()