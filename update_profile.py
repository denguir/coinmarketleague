import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coinmarketleague.settings")
import django
django.setup()

from django.contrib.auth.models import User
from traderboard.models import TradingAccount
from Market import Market
from datetime import datetime, timezone
from traderboard.tasks import take_snapshot, update_profile


__PLATFORMS__ = ['Binance']


if __name__ == '__main__':
    # Take time snapshot of market state
    now = datetime.now(timezone.utc)
    today = datetime.combine(now, datetime.min.time(), timezone.utc)
    markets = {platform : Market.trading_from(platform) for platform in __PLATFORMS__}
    users = User.objects.all()

    for user in users:
        # Collect account level data
        tas = TradingAccount.objects.filter(user=user)
        for ta in tas:
            try:
                take_snapshot(ta, markets[ta.platform], now)
            except Exception as e:
                print(f"Error processing {ta.id}.")
                print(e)
            # async_task(update_order_history, (ta, now, markets[ta.platform]), ack_failure=True)
            # async_task(update_transaction_history, ta, now, markets[ta.platform], timeout=120, ack_failure=True)
        # Collect user level data
        update_profile(user, markets, today)