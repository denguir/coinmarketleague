from django.db import models
from django.contrib.auth.models import User
from encrypted_fields import fields
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_confirmed = models.BooleanField(default=False)
    # store main stats about the user
    daily_pnl = models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)
    weekly_pnl = models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)
    monthly_pnl = models.DecimalField(max_digits=9, decimal_places=2, default=None, null=True)

# TODO:
# create ProfileSnapshot that pre-aggregates from user's SnapshotAccount
# common statistics -> reduces the amount of live calculations

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

# see:
# https://simpleisbetterthancomplex.com/tutorial/2016/07/22/how-to-extend-django-user-model.html
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()