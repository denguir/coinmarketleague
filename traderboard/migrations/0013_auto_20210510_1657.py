# Generated by Django 3.0.7 on 2021-05-10 16:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('traderboard', '0012_auto_20210508_0808'),
    ]

    operations = [
        migrations.AlterField(
            model_name='snapshotaccount',
            name='created_at',
            field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name='snapshotaccount',
            name='updated_at',
            field=models.DateTimeField(),
        ),
    ]
