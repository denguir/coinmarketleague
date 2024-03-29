# Generated by Django 3.0.7 on 2021-03-27 15:27

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('traderboard', '0002_auto_20210325_1352'),
    ]

    operations = [
        migrations.RenameField(
            model_name='snapshotaccount',
            old_name='balance_usdt',
            new_name='balance_usd',
        ),
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('daily_pnl', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('weekly_pnl', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('monthly_pnl', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
