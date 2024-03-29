# Generated by Django 3.2.1 on 2021-09-11 10:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('traderboard', '0024_auto_20210909_1809'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='accounttransactions',
            constraint=models.UniqueConstraint(fields=('account', 'created_at', 'asset', 'amount', 'side'), name='No transaction duplicate'),
        ),
    ]
