from django.db import models
from django.contrib.auth import get_user_model
from django_cryptography.fields import encrypt

from django.db.models import Q
from django.db.models.functions import Extract

import decimal
import datetime
import math

class Credential(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    bank = encrypt(models.CharField(max_length=200))
    username = encrypt(models.CharField(max_length=200))
    password = encrypt(models.CharField(max_length=200))
    pin = encrypt(models.CharField(max_length=200, blank=True))
    active = models.BooleanField(default=True)
    objects = models.Manager()


class Account(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, null=True, default=None)
    name = models.CharField(max_length=100, blank=True)
    credential = models.ForeignKey(Credential, on_delete=models.CASCADE, null=True, default=None, blank=True)
    balance = models.DecimalField(max_digits=50, decimal_places=2, default=0)
    limit = models.DecimalField(max_digits=50, decimal_places=2, null=True)
    true_balance = models.DecimalField(max_digits=50, decimal_places=2, default=0)
    last_updated = models.DateTimeField(default=datetime.datetime(1, 1, 1))
    ACCOUNT_GROUPS = (
        ('transactional', 'transactional'),
        ('saving', 'saving'),
        ('debt', 'debt')
    )

    ACCOUNT_TYPES = (
        ('cheque', 'cheque'),
        ('credit', 'credit'),
    )
    account_type = models.CharField(choices=ACCOUNT_TYPES, max_length=50, blank=True)
    account_group = models.CharField(choices=ACCOUNT_GROUPS, max_length=50, blank=True)
    objects = models.Manager()

    def __unicode__(self):
        return self.name + ' ' + str(self.true_balance)

    def __str__(self):
        return self.name + ' ' + str(self.true_balance)

    def get_related_transactions(self):
        """Get transactions on this account ordered by day of month"""
        account_query = Q(account_from=self) | Q(account_to=self)
        # Changes involving this account
        changes = Transaction.objects.annotate(
            month_from_day=Extract('month_from', 'day')
        ).filter(account_query).order_by('month_from_day')
        return changes


class Item(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)

    def __unicode__(self):
        return self.name + ' ' + str(self.user.email)

    def __str__(self):
        return self.name + ' ' + str(self.user.email)

def month_later_this_date(this_date, day, months):
    """Again months here should be less than 12"""
    next_month = (this_date.month % 12) + months
    while next_month >= 13:
        next_month -= 12
    if next_month == 0:
        next_month = 12
    if this_date.month + months >= 13:
        next_year = this_date.year + 1
    else:
        next_year = this_date.year
    if day > 28 and next_month == 2:
        day = 28
    if day > 30 and (next_month == 9 or next_month == 6 or next_month == 4):
        day = 30
    return datetime.date(next_year, next_month, day)

def month_after_this_date(this_date, day):
    next_month = (this_date.month % 12) + 1
    if this_date.month == 12:
        next_year = this_date.year + 1
    else:
        next_year = this_date.year
    if day > 28 and next_month == 2:
        day = 28
    if day > 30 and (next_month == 9 or next_month == 6 or next_month == 4 or next_month == 11):
        day = 30
    return datetime.date(next_year, next_month, day)

def month_before_this_date(this_date, day):
    next_month = this_date.month - 1
    if next_month == 0:
        next_month = 12
        next_year = this_date.year - 1
    else:
        next_year = this_date.year
    if day > 28 and next_month == 2:
        day = 28
    if day > 30 and (next_month == 9 or next_month == 6 or next_month == 4 or next_month == 11):
        day = 30
    return datetime.date(next_year, next_month, day)

class Transaction(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, null=True, default=None, blank=True)
    account_from = models.ForeignKey(Account, on_delete=models.CASCADE)
    # this is for transfers to credit cards or savings accounts
    account_to = models.ForeignKey(Account, related_name='transfers', on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    value = models.DecimalField(max_digits=50, decimal_places=2, default=0)
    recurring = models.BooleanField(default=True)
    month_from = models.DateField(default=datetime.date.today)
    month_to = models.DateField(default=datetime.date.today, null=True, blank=True)
    objects = models.Manager()

    # transaction where its value increases by a certain percentage every certain number of months
    increase_multiplier = models.DecimalField(max_digits=9, decimal_places=3, default=1)
    increase_month_interval = models.IntegerField(default=1)
    increase_first_interval = models.IntegerField(default=0)
    increase_start_date = models.DateField(default=None, null=True, blank=True)
    # interest transaction
    interest_rate = models.DecimalField(max_digits=9, decimal_places=3, default=0)
    has_interest_below_zero = models.BooleanField(default=False)
    def __unicode__(self):
        return self.name + ' ' + str(self.value)

    def __str__(self):
        return self.name + ' ' + str(self.value)

    def in_month(self, date):
        if self.recurring:
            if date.year < self.month_from.year:
                return False
            if date.year == self.month_from.year and date.month < self.month_from.month:
                return False
            else:
                return True

        if date.year < self.month_from.year:
            return False
        month_to=self.month_to
        if self.month_to is None:
            month_to = self.month_from
        if date.year > month_to.year:
            return False
        if date.year == self.month_from.year and date.month < self.month_from.month:
            return False
        if date.year == month_to.year and date.month > month_to.month:
            return False
        return True

    def natural_values_for_dates(self, dates):
        def value_for_date(date):
            self_value = self.value
            if self.interest_rate > 0:
                self_value = decimal.Decimal(1.0)
            
            date_value = decimal.Decimal(0.0)
            if not self.in_month(date):
                return decimal.Decimal(0.0)
            
            date_value = self_value
            
            if self.increase_start_date is None:
                return date_value
            
            month_difference = ((date.year - self.increase_start_date.year) * 12) + date.month - self.increase_start_date.month
            if month_difference <= 0:
                return date_value
            x = 0
            if self.increase_first_interval <= 0:
                x = math.floor(month_difference / self.increase_month_interval)
            elif self.increase_first_interval > 0:
                x = math.floor((month_difference + (self.increase_month_interval - self.increase_first_interval)) / self.increase_month_interval)
            if x < 0:
                x = 0
            # multiply date_value by the correct number of multipliers for where it is in the range from the first date
            return round(date_value * decimal.Decimal(math.pow(self.increase_multiplier, x)), 2)
        
        value_list = list(map(value_for_date, dates))
        return value_list


    def values_for_dates(self, dates, for_from=False):
        def value_for_date(date):
            self_value = self.value
            if self.interest_rate > 0:
                self_value = decimal.Decimal(1.0)

            date_value = decimal.Decimal(0.0)
            if not self.in_month(date):
                return decimal.Decimal(0.0)
            
            if for_from and self.account_to:
                date_value = -self_value
            else:
                date_value = self_value
            
            if self.increase_start_date is None:
                return date_value
            
            month_difference = ((date.year - self.increase_start_date.year) * 12) + date.month - self.increase_start_date.month
            if month_difference <= 0:
                return date_value
            x = 0
            if self.increase_first_interval <= 0:
                x = math.floor(month_difference / self.increase_month_interval)
            elif self.increase_first_interval > 0:
                x = math.floor((month_difference + (self.increase_month_interval - self.increase_first_interval)) / self.increase_month_interval)
            if x < 0:
                x = 0
            # multiply date_value by the correct number of multipliers for where it is in the range from the first date
            return round(date_value * decimal.Decimal(math.pow(self.increase_multiplier, x)), 2)

        value_list = list(map(value_for_date, dates))
        return value_list

    def move_from_to_month_after(self, this_day):
        old_month_from = self.month_from
        old_month_from.month = (this_day.month % 12) + 1
        self.month_from.month = old_month_from
        self.save()

    def create_simple_transaction(self, value, month_index):
        new_month = month_later_this_date(datetime.date.today(), self.month_from.day, month_index)
        new_transaction = Transaction(account_from=self.account_from,
                                      account_to=self.account_to,
                                      name=self.name,
                                      value=value,
                                      recurring=False,
                                      month_from=new_month,
                                      month_to=new_month)
        return new_transaction

    def create_new_with_month_after_end(self, this_day):
        new_transaction = Transaction(account_from=self.account_from,
                                      account_to=self.account_to,
                                      name=self.name,
                                      value=self.value,
                                      recurring=False,
                                      month_from=self.month_from,
                                      month_to=month_before_this_date(this_day, self.month_from.day),
                                      increase_multiplier=self.increase_multiplier,
                                      increase_month_interval=self.increase_month_interval,
                                      increase_start_date=self.increase_start_date,
                                      increase_first_interval=self.increase_first_interval)
        return new_transaction
