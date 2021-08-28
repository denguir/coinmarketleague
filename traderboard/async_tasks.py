from celery import shared_task
from Market import Market
from decimal import Decimal
from asgiref.sync import sync_to_async
from .models import TradingAccount, AccountTrades, AccountTransactions

@shared_task
def add(x, y):
    return x + y


@sync_to_async(thread_sensitive=True)
def record_transaction(event, ta):
    if TradingAccount.objects.get(id=ta.id):
        asset = event['a']
        amount = Decimal(event['d'])
        side = 'DEPOSIT' if amount >= 0 else 'WITHDRAWAL'
        date = Market.to_datetime(event['E'])
        trans = AccountTransactions(account=ta,
                                    created_at=date,
                                    updated_at=date,
                                    asset=asset,
                                    amount=abs(amount),
                                    side=side
                                    )
        trans.save()
        print('transaction recorded.')

    else:
        raise Exception(f'Trading account {ta.id} has been deleted.')


@sync_to_async(thread_sensitive=True)
def record_trade(event, ta):
    if TradingAccount.objects.get(id=ta.id):
        symbol = event['s']
        side = event['S']
        quantity = Decimal(event['q'])
        price = Decimal(event['p'])
        date = Market.to_datetime(event['E'])

        trade = AccountTrades(account=ta,
                            created_at=date,
                            updated_at=date,
                            symbol=symbol,
                            amount=quantity,
                            price=price,
                            side=side,
                            )
        trade.save()
        print('trade recorded.')

    else:
        raise Exception(f'Trading account {ta.id} has been deleted.')