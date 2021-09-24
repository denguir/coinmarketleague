from django.db import models
from django.contrib.auth.models import User
from encrypted_fields import fields
from django.db.models.signals import post_save
from django.dispatch import receiver


class TradingPlatform(models.TextChoices):
    BINANCE = 'Binance'


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # main settings
    public = models.BooleanField(default=False)
    picture = models.ImageField(upload_to='profile_picture', blank=True)

    # store main stats about the user
    daily_pnl = models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)
    weekly_pnl = models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)
    monthly_pnl = models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)
    

class TradingAccount(models.Model):
    '''Trading account of a given User on a supported TradingPlatform'''

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    platform = models.CharField(max_length=100,
                                choices=TradingPlatform.choices,
                                default=TradingPlatform.BINANCE)

    api_key = models.CharField(max_length=64, default='')
    api_secret = fields.EncryptedCharField(max_length=64, default='')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['api_key', 'platform'],     
                                    name='No api_key duplicate')
        ]


class SnapshotAccount(models.Model):
    '''Contains raw stats about the user'''
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    # balance value
    balance_btc = models.DecimalField(max_digits=30, decimal_places=10, default=None, null=True)
    balance_usdt = models.DecimalField(max_digits=30, decimal_places=10)
    # absolute PnL wrt last snapshot
    pnl_btc =  models.DecimalField(max_digits=30, decimal_places=10, default=None, null=True)
    pnl_usdt =  models.DecimalField(max_digits=30, decimal_places=10, default=None, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'created_at'], 
                                    name='No snapshot duplicate')
        ]


class SnapshotAccountDetails(models.Model):
    '''Details of SnapshotAccount containing, the asset, amount pairs
    available at snapshot time''' 
    snapshot = models.ForeignKey(SnapshotAccount, on_delete=models.CASCADE)
    asset = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=30, decimal_places=10)
    price_usdt = models.DecimalField(max_digits=30, decimal_places=10, default=None, null=True)
    price_btc = models.DecimalField(max_digits=30, decimal_places=10, default=None, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['snapshot', 'asset'], 
                                    name='No detail duplicate')
        ]


class AccountTrades(models.Model):
    '''Historic of trading moves of TradingAccount'''
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    symbol = models.CharField(max_length=20, default='Unknown')
    amount = models.DecimalField(max_digits=30, decimal_places=10)
    price = models.DecimalField(max_digits=30, decimal_places=10)
    side = models.CharField(max_length=10)


class AccountTransactions(models.Model):
    '''Historic of transactions of TradingAccount'''
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    asset = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=30, decimal_places=10)
    side = models.CharField(max_length=10)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'created_at', 'asset', 'amount', 'side'], 
                                    name='No transaction duplicate')
        ]


class SnapshotMarket(models.Model):
    '''Snapshot of the Market prices'''
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    platform = models.CharField(max_length=100,
                                choices=TradingPlatform.choices,
                                default=TradingPlatform.BINANCE)

    symbol = models.CharField(max_length=20, default='Unknown')
    asset = models.CharField(max_length=20, default='Unknown')
    base = models.CharField(max_length=20, default='Unknown')
    price = models.DecimalField(max_digits=30, decimal_places=10)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()