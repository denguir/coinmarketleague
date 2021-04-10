from django.db import models
from django.contrib.auth.models import User
from encrypted_fields import fields
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # main settings
    public = models.BooleanField(default=False)
    # store main stats about the user
    daily_pnl = models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)
    weekly_pnl = models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)
    monthly_pnl = models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)


class SnapshotProfile(models.Model):
    '''Contains pre-aggregate stats about the user'''
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # balance value
    balance_btc = models.DecimalField(max_digits=30, decimal_places=8)
    balance_usdt = models.DecimalField(max_digits=30, decimal_places=2)
    # these are profit and losses from the last snapshot: pnl(t-1; t),
    # note that pnl(t-2; t) = pnl(t-2; t-1) + pnl(t-1; t) * bal(t-1)/bal(t-2)
    pnl_btc =  models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)
    pnl_usdt =  models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)


class SnapshotProfileDetails(models.Model):
    '''Details of SnapshotProfile containing, the asset, amount pairs
    available at snapshot time''' 
    snapshot = models.ForeignKey(SnapshotProfile, on_delete=models.CASCADE)
    asset = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=30, decimal_places=8)


class TradingAccount(models.Model):
    '''Trading account of a given User on a supported TradingPlatform'''
    class TradingPlatform(models.TextChoices):
        BINANCE = 'Binance'

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    platform = models.CharField(max_length=100,
                                choices=TradingPlatform.choices,
                                default=TradingPlatform.BINANCE)

    # about encrypted fields: https://pypi.org/project/django-searchable-encrypted-fields/
    api_key = models.CharField(max_length=64, default='')
    api_secret = fields.EncryptedCharField(max_length=64, default='')


class SnapshotAccount(models.Model):
    '''Snapshot of a TradingAccount with balance value'''
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    balance_btc =  models.DecimalField(max_digits=30, decimal_places=8)
    balance_usdt = models.DecimalField(max_digits=30, decimal_places=2)


class SnapshotAccountDetails(models.Model):
    '''Details of SnapshotAccount containing, the asset, amount pairs
    available at snapshot time''' 
    snapshot = models.ForeignKey(SnapshotAccount, on_delete=models.CASCADE)
    asset = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=30, decimal_places=8)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()