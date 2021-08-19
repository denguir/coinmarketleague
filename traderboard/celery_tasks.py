from celery import shared_task

@shared_task
def add(x, y):
    return x + y


@shared_task
def record_transaction(event, ta):
    asset = event['a']
    amount = float(event['d'])
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


@shared_task
def record_trade(event, ta):
    symbol = event['s']
    side = event['S']
    quantity = float(event['q'])
    price = float(event['p'])
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