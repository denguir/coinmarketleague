# Generated by Django 3.0.7 on 2021-04-10 12:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('traderboard', '0009_auto_20210403_1450'),
    ]

    operations = [
        migrations.AddField(
            model_name='snapshotprofile',
            name='pnl_btc',
            field=models.DecimalField(decimal_places=2, default=None, max_digits=9, null=True),
        ),
    ]
