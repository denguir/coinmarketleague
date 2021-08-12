from django.db import models
from django.contrib.auth.models import User
from encrypted_fields import fields
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # main settings
    public = models.BooleanField(default=False)
    picture = models.ImageField(upload_to='profile_picture', blank=True)

    # store main stats about the user
    daily_pnl = models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)
    weekly_pnl = models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)
    monthly_pnl = models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)

    # number of trading accounts linked to user 
    nacc = models.IntegerField(default=0, min_value=0) 


class TradingAccount(models.Model):
    '''Trading account of a given User on a supported TradingPlatform'''
    class TradingPlatform(models.TextChoices):
        BINANCE = 'Binance'

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    platform = models.CharField(max_length=100,
                                choices=TradingPlatform.choices,
                                default=TradingPlatform.BINANCE)

    api_key = models.CharField(max_length=64, default='')
    api_secret = fields.EncryptedCharField(max_length=64, default='')


class SnapshotAccount(models.Model):
    '''Contains raw stats about the user'''
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    # balance value
    balance_btc = models.DecimalField(max_digits=30, decimal_places=8, default=None, null=True)
    balance_usdt = models.DecimalField(max_digits=30, decimal_places=2)
    # absolute PnL wrt last snapshot
    pnl_btc =  models.DecimalField(max_digits=30, decimal_places=8, default=None, null=True)
    pnl_usdt =  models.DecimalField(max_digits=30, decimal_places=2, default=None, null=True)


class SnapshotAccountDetails(models.Model):
    '''Details of SnapshotAccount containing, the asset, amount pairs
    available at snapshot time''' 
    snapshot = models.ForeignKey(SnapshotAccount, on_delete=models.CASCADE)
    asset = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=30, decimal_places=8)


class AccountTrades(models.Model):
    '''Historic of trading moves of TradingAccount'''
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    asset = models.CharField(max_length=10)
    base = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=30, decimal_places=8)
    price = models.DecimalField(max_digits=30, decimal_places=8)
    side = models.CharField(max_length=10)


class AccountTransactions(models.Model):
    '''Historic of transactions of TradingAccount'''
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    asset = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=30, decimal_places=8)
    side = models.CharField(max_length=10)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()