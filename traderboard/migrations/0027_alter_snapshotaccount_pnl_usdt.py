# Generated by Django 3.2.1 on 2021-09-18 12:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('traderboard', '0026_alter_snapshotaccount_balance_usdt'),
    ]

    operations = [
        migrations.AlterField(
            model_name='snapshotaccount',
            name='pnl_usdt',
            field=models.DecimalField(decimal_places=10, default=None, max_digits=30, null=True),
        ),
    ]
