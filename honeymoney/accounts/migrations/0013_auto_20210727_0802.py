# Generated by Django 2.1 on 2021-07-27 08:02

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_account_account_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='increase_first_interval',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='transaction',
            name='increase_month_interval',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='transaction',
            name='increase_multiplier',
            field=models.DecimalField(decimal_places=3, default=1, max_digits=9),
        ),
        migrations.AddField(
            model_name='transaction',
            name='increase_start_date',
            field=models.DateField(blank=True, default=datetime.date.today, null=True),
        ),
    ]