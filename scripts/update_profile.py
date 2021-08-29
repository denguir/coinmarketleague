from django.contrib.auth.models import User
from traderboard.models import TradingAccount
from Market import Market
from datetime import datetime, timezone
from traderboard.tasks import take_snapshot, update_profile


__PLATFORMS__ = ['Binance']


def run():
    # Take time snapshot of market state
    now = datetime.now(timezone.utc)
    markets = {platform : Market.connect(platform) for platform in __PLATFORMS__}
    users = User.objects.all()

    for user in users:
        # Collect account level data
        tas = TradingAccount.objects.filter(user=user)
        for ta in tas:
            try:
                take_snapshot(ta, markets[ta.platform], now)
            except Exception as e:
                print(f"Error during snapshot of {ta.user.username} - account {ta.id}.")
                print(e)
        # Collect user level data
        update_profile(user, markets, now)