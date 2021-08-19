# Generated by Django 3.2.1 on 2021-08-18 10:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('traderboard', '0017_auto_20210605_1144'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='accounttrades',
            name='asset',
        ),
        migrations.RemoveField(
            model_name='accounttrades',
            name='base',
        ),
        migrations.AddField(
            model_name='accounttrades',
            name='symbol',
            field=models.CharField(default='Unknown', max_length=20),
        ),
    ]
