# Generated by Django 3.0.7 on 2021-03-29 11:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('traderboard', '0005_auto_20210328_1351'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='email_confirmed',
            field=models.BooleanField(default=False),
        ),
    ]
