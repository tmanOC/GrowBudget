# Generated by Django 2.1 on 2021-08-05 14:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_auto_20210727_0815'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='interest_rate',
            field=models.DecimalField(decimal_places=3, default=0, max_digits=9),
        ),
    ]
