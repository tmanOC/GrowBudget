# Generated by Django 2.1 on 2018-08-24 16:23

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_cryptography.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Credential',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bank', django_cryptography.fields.encrypt(models.CharField(max_length=200))),
                ('username', django_cryptography.fields.encrypt(models.CharField(max_length=200))),
                ('password', django_cryptography.fields.encrypt(models.CharField(max_length=200))),
                ('pin', django_cryptography.fields.encrypt(models.CharField(max_length=200))),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
