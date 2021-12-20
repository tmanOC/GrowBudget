from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.views import generic
from .models import Account, Credential, Transaction, month_after_this_date
from django.db.models import Q
from fetcher.fetcher.fetch_job import FetchCronJob

from django.views.generic.edit import CreateView
from django.views.generic.edit import UpdateView
from django.views.generic.edit import DeleteView
from django.views.generic.base import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.functions import Extract
from django.db.models.query import QuerySet

from django import forms
from django.forms import widgets
from django.views.generic.edit import BaseCreateView

import datetime
import decimal
import copy
import pprint

def refresh_accounts(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse('home'))
    if not request.user.is_staff:
        return HttpResponseRedirect(reverse('accounts:index'))
    job = FetchCronJob()
    job.do()
    return HttpResponseRedirect(reverse('accounts:index'))


def months_days_from_day(today, months=12):
    dates = []
    y = today.year
    for x in range(months):
        m = (today.month + x - 1) % 12 + 1
        if m == 1 and x != 0:
            y += 1
        d = 1
        dates.append(datetime.date(y, m, d))
    return dates


def month_strings_from_dates(dates):
    return list(map(lambda x: x.strftime('%b'), dates))

def year_strings_from_dates(dates):
    return list(map(lambda x: x.strftime('%Y'), dates))


def balances_for(month, change_objects, balance_start, min_balance=0):
    balance = balance_start
    balances = []
    error_messages = []
    for j in range(len(change_objects)):
        balance += decimal.Decimal(change_objects[j]['values'][month])
        balances.append(balance)
        if balance < min_balance:
            error_messages.append('negative balance ' + str(balance) + ' at ' + change_objects[j]['name'] + ' ' + str(month))
    return balances, error_messages

def balances_from_balances3d(month, balances3d):
     # This is the 2d array of balances for that particular month
    balances = []
    for balances1d in balances3d[month][1:]:
        balances.append(balances1d[-1])
    
    return (balances, [])

def all_accounts_balances_for(month, change_objects, balances_start, accounts_objects, min_balance=0):
    """Returns the balances after the changes to all the balances in balances_start."""
    account_balances2d = [balances_start]

    for obj_change in change_objects:
        new_balances = account_balances2d[-1].copy()
        try:
            account_from_index = accounts_objects.index(obj_change['account_from'])
    
            # if the change object is interest, I need to figure out the value on the fly.
            new_balances[account_from_index] += obj_change['values'][month]
            if 'interest_rate' in obj_change and len(obj_change['values']) > month + 1:
                interest_value = ((new_balances[account_from_index] - obj_change['account_from'].limit) * (obj_change['interest_rate']/100))/12
                if obj_change['has_interest_below_zero'] and interest_value < decimal.Decimal(0):
                    obj_change['values'][month + 1] = round(obj_change['values'][month + 1] * interest_value,2)
                elif (not obj_change['has_interest_below_zero']) and interest_value > decimal.Decimal(0):
                    obj_change['values'][month + 1] = round(obj_change['values'][month + 1] * interest_value,2)
                else:
                    obj_change['values'][month + 1] = 0
        except ValueError:
            if obj_change['account_to'] is not None:
                print('hello')
                try:
                    account_to_index = accounts_objects.index(obj_change['account_to'])
                    new_balances[account_to_index] -= obj_change['values'][month]
                    new_balances[-1] -= obj_change['values'][month]
                    account_balances2d.append(new_balances)
                    print(new_balances)
                    continue
                except ValueError:
                    account_balances2d.append(new_balances)
                    continue
            else:
                account_balances2d.append(new_balances)
                continue

        if obj_change['account_to'] is not None:
            try:
                account_to_index = accounts_objects.index(obj_change['account_to'])
                new_balances[account_to_index] -= obj_change['values'][month]
            except ValueError:
                new_balances[-1] += obj_change['values'][month]
                pass
        else:
            new_balances[-1] += obj_change['values'][month]
        account_balances2d.append(new_balances)
    
    return account_balances2d

class IndexView(generic.ListView, LoginRequiredMixin):
    template_name = 'accounts/index.html'
    context_object_name = 'accounts_list'

    def get_queryset(self):
        """Return the accounts for this user's credentials"""
        user = self.request.user
        credentials = Credential.objects.filter(user=self.request.user)
        account_query = Q()

        for c in credentials:
            account_query = account_query | Q(credential=c)

        if len(credentials) == 0:
            return Account.objects.none()
        accounts = Account.objects.filter(account_query)
        return accounts


class DetailView(generic.DetailView, LoginRequiredMixin):
    model = Account
    template_name = 'accounts/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        dates = months_days_from_day(datetime.date.today())
        context['months'] = month_strings_from_dates(dates)
        
        account = context['object']
        changes = account.get_related_transactions()

        change_objects = []
        for c in changes:
            change_objects.append({'name': c.name, 'values': c.values_for_dates(dates, c.account_from_id == account.id)})

        context['transaction_list'] = change_objects

        balance_objects = []
        for c in change_objects:
            balance_objects.append({'name': c['name'], 'balances': []})

        error_messages = []
        balances = [account.balance]

        for i in range(12):
            (array_balances, errors) = balances_for(month=i, change_objects=change_objects, balance_start=balances[i])
            error_messages = error_messages + errors
            for j in range(len(array_balances)):
                balance_objects[j]['balances'].append(array_balances[j])
            balances.append(array_balances[len(array_balances) - 1])

        context['balances'] = balances
        context['balance_list'] = balance_objects
        context['error_messages'] = error_messages
        return context


def add_in_change_object(new_object, old_objects):
    for current_change in old_objects:
        if current_change['name'] == new_object['name']:
            current_change['values'] = [sum(pair) for pair in zip(current_change['values'], new_object['values'])]
            return True
    old_objects.append(new_object)
    return False

def add_in_change_object_with_accounts(new_object, old_objects):
    for current_change in old_objects:
        if current_change['name'] == new_object['name'] and current_change['account_from'] == new_object['account_from'] and current_change['account_to'] == new_object['account_to']:
            current_change['values'] = [sum(pair) for pair in zip(current_change['values'], new_object['values'])]
            return True
    old_objects.append(new_object)
    return False


class NewDetailView(generic.DetailView, LoginRequiredMixin):
    model = Account
    template_name = 'accounts/detail.html'

    def post(self, request, pk):
        transaction_name = request.POST['transactionName']
        if not transaction_name:
            return HttpResponseRedirect(redirect_to=reverse('accounts:new-detail', kwargs={'pk': pk}))
        query = (Q(account_from__id=pk) | Q(account_to__id=pk)) & (Q(name=transaction_name) | Q(item__name=transaction_name))
        changes = Transaction.objects.filter(query)
        this_day = datetime.date.today()

        for c in changes:
            if not c.in_month(this_day):
                continue
            if c.recurring:
                c.month_from = month_after_this_date(this_day, c.month_from.day)
                c.save()
                continue
            day_next_month = month_after_this_date(this_day, this_day.day)
            if c.in_month(day_next_month):
                c.month_from = month_after_this_date(this_day, c.month_from.day)
                c.save()
                continue
            c.delete()

        return HttpResponseRedirect(redirect_to=reverse('accounts:new-detail', kwargs={'pk': pk}))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year = 0
        if 'year' in self.request.GET:
            year = int(self.request.GET['year'])
        dates = months_days_from_day(datetime.date.today(),(year+1)*12)
        context['months'] = month_strings_from_dates(dates[-12:])
        context['year_strings'] = year_strings_from_dates(dates[-12:])
        
        account = context['object']
        changes = account.get_related_transactions()

        change_objects = []
        viewing_change_objects = []
        for c in changes:
            if c.item:
                name = c.item.name
            else:
                name = c.name

            possible_element = {'name': name, 'values': c.values_for_dates(dates, c.account_from_id == account.id), 'range': range(len(dates))}
            add_in_change_object(possible_element, change_objects)
            add_in_change_object(copy.deepcopy(possible_element), viewing_change_objects)

        for myObj in viewing_change_objects:
            myObj['values'] = myObj['values'][-12:]
            myObj['range'] = range(len(dates)-12, len(dates))

        context['transaction_list'] = viewing_change_objects

        balance_objects = []
        for c in change_objects:
            balance_objects.append({'name': c['name'], 'balances': []})

        error_messages = []
        balances = [account.balance]

        for i in range((year+1)*12):
            (array_balances, errors) = balances_for(month=i, change_objects=change_objects, balance_start=balances[i])
            error_messages = error_messages + errors
            for j in range(len(array_balances)):
                balance_objects[j]['balances'].append(array_balances[j])
            balances.append(array_balances[len(array_balances) - 1])

        context['balances'] = balances[-13:-1]
        for balance_object in balance_objects:
            balance_object['balances'] = balance_object['balances'][-12:]
        context['balance_list'] = balance_objects
        context['error_messages'] = error_messages
        return context


class TransactionalDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/detail.html'

    def post(self, request):
        transaction_name = request.POST['transactionName']
        if not transaction_name:
            return HttpResponseRedirect(redirect_to=reverse('accounts:transactional-detail'))
        query = (Q(name=transaction_name) | Q(item__name=transaction_name))
        changes = Transaction.objects.filter(query)
        this_day = datetime.date.today()

        for c in changes:
            if not c.in_month(this_day):
                continue
            if c.recurring:
                c.month_from = month_after_this_date(this_day, c.month_from.day)
                c.save()
                continue
            day_next_month = month_after_this_date(this_day, this_day.day)
            if c.in_month(day_next_month):
                c.month_from = month_after_this_date(this_day, c.month_from.day)
                c.save()
                continue
            c.delete()

        return HttpResponseRedirect(redirect_to=reverse('accounts:transactional-detail'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year = 0
        if 'year' in self.request.GET:
            year = int(self.request.GET['year'])
        
        context['account'] = {'name': 'All Accounts'}
        user = self.request.user


        accounts = Account.objects.filter(user=user, account_group='transactional') if user.is_authenticated else []

        account_query = Q()
        total_balance = 0
        context['accounts'] = []
        account_start_balances = []
        for ac in accounts:
            context['accounts'].append(ac)
            account_query = account_query | (Q(account_from=ac) & Q(account_to=None))
            # account_to is not one of the transactional accounts
            account_query = account_query | (Q(account_from=ac) & ~Q(account_to__in=accounts))
            # account_from is not one of the transactional accounts
            account_query = account_query | (~Q(account_from__in=accounts) & Q(account_to=ac))
            total_balance = total_balance + ac.true_balance
            account_start_balances.append(ac.true_balance)
        account_start_balances.append(total_balance)
        if len(context['accounts']) == 0:
            changes = Transaction.objects.none()
        else:
            changes = Transaction.objects.annotate(
                month_from_day=Extract('month_from', 'day')
            ).filter(account_query).order_by('month_from_day')
        
        dates = months_days_from_day(datetime.date.today(),(year+1)*12)
        context['months'] = month_strings_from_dates(dates[-12:])
        context['year_strings'] = year_strings_from_dates(dates[-12:])
        
        change_objects = []
        for c in changes:
            if c.item:
                name = c.item.name
            else:
                name = c.name
            possible_element = {'name': name,
                                'values': c.natural_values_for_dates(dates),
                                'range': range(len(dates)),
                                'account_from': c.account_from,
                                'account_to': c.account_to}
            # make a new change object for every interest change
            if c.interest_rate > 0:
                # make new change object
                change_values = c.natural_values_for_dates(dates)
                
                if change_values[0] == 1:
                    change_values[0] = c.value
                change_objects.append({'name': name,
                                       'interest_rate': c.interest_rate,
                                       'has_interest_below_zero': c.has_interest_below_zero,
                                       'values': change_values,
                                       'range': range(len(dates)),
                                       'account_from': c.account_from,
                                       'account_to': c.account_to})
                
            else:
                add_in_change_object_with_accounts(possible_element, change_objects)
                # add_in_change_object_with_accounts(copy.deepcopy(possible_element), viewing_change_objects)
            
        # This is fine, the problem is that interest change objects are not shown
        
        
        accounts_objects = context['accounts']

        # change_objects
        account_balances3d = []
        for i in range((year+1)*12):
            account_balances2d = all_accounts_balances_for(i, change_objects, account_start_balances, accounts_objects, min_balance=0)
            account_start_balances = account_balances2d[-1]
            account_balances3d.append(account_balances2d)
        
        balance_objects = []
        for c in change_objects:
            balance_objects.append({'name': c['name'], 'balances': []})

        error_messages = []
        balances = [total_balance]

        if 'threshold' in self.request.GET:
            threshold_balance = self.request.GET['threshold']
            threshold_balance = decimal.Decimal(threshold_balance)
        else:
            threshold_balance = 0

        if len(context['accounts']) == 0 or len(change_objects) == 0:
            context['balances'] = balances
            context['balance_list'] = balance_objects
            context['error_messages'] = error_messages
            return context

        for i in range((year+1)*12):
            (array_balances, errors) = balances_from_balances3d(i, account_balances3d)
            error_messages = error_messages + errors
            for j in range(len(array_balances)):
                balance_objects[j]['balances'].append(array_balances[j])
            balances.append(array_balances[len(array_balances) - 1])


        context['balances'] = balances[-13:-1]
        for balance_object in balance_objects:
            balance_object['balances'] = balance_object['balances'][-12:]
        context['balance_list'] = balance_objects
        context['error_messages'] = error_messages

        viewing_change_objects = copy.deepcopy(change_objects)
        for myObj in viewing_change_objects:
            myObj['values'] = myObj['values'][-12:]
            myObj['range'] = range(len(dates)-12, len(dates))
        context['transaction_list'] = viewing_change_objects

        return context


class IndividualAccountDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/detail.html'

    def post(self, request, pk):
        transaction_name = request.POST['transactionName']
        if not transaction_name:
            return HttpResponseRedirect(redirect_to=reverse('accounts:full-detail'))
        query = (Q(name=transaction_name) | Q(item__name=transaction_name))
        changes = Transaction.objects.filter(query)
        this_day = datetime.date.today()

        for c in changes:
            if not c.in_month(this_day):
                continue
            if c.recurring:
                c.month_from = month_after_this_date(this_day, c.month_from.day)
                c.save()
                continue
            day_next_month = month_after_this_date(this_day, this_day.day)
            if c.in_month(day_next_month):
                c.month_from = month_after_this_date(this_day, c.month_from.day)
                c.save()
                continue
            c.delete()

        return HttpResponseRedirect(redirect_to=reverse('accounts:full-detail'))

    def get_context_data(self, **kwargs):
        # how do I get account here again?
        context = super().get_context_data(**kwargs)
        user = self.request.user
        account = Account.objects.get(user=user, pk=context['pk']) if user.is_authenticated else None
        year = 0
        if 'year' in self.request.GET:
            year = int(self.request.GET['year'])
        
        context['account'] = {'name': account.name}
        
        accounts = [account]

        account_query = Q()
        total_balance = 0
        context['accounts'] = []
        account_start_balances = []
        for ac in accounts:
            context['accounts'].append(ac)
            total_balance = total_balance + ac.balance
            account_start_balances.append(ac.balance)
            account_query = account_query | (Q(account_from=ac) & Q(account_to=None))
            # account_to is not one of the transactional accounts
            account_query = account_query | (Q(account_from=ac) & ~Q(account_to__in=accounts))
            # account_from is not one of the transactional accounts
            account_query = account_query | (~Q(account_from__in=accounts) & Q(account_to=ac))
        
        account_start_balances.append(total_balance)

        if len(context['accounts']) == 0:
            changes = Transaction.objects.none()
        else:
            changes = Transaction.objects.annotate(
                month_from_day=Extract('month_from', 'day')
            ).filter(account_query).order_by('month_from_day')
        
        dates = months_days_from_day(datetime.date.today(),(year+1)*12)
        context['months'] = month_strings_from_dates(dates[-12:])
        context['year_strings'] = year_strings_from_dates(dates[-12:])
        
        # loop through all the months
        # loop through all change objects
        # for i in range((year+1)*12):
        # keep track of all account balances with every object change as well as total
        # build up output objects

        change_objects = []
        viewing_change_objects = []
        for c in changes:
            if c.item:
                name = c.item.name
            else:
                name = c.name
            possible_element = {'name': name,
                                'values': c.natural_values_for_dates(dates),
                                'range': range(len(dates)),
                                'account_from': c.account_from,
                                'account_to': c.account_to}
            # make a new change object for every interest change
            if c.interest_rate > 0:
                # make new change object
                change_values = c.natural_values_for_dates(dates)
                
                if change_values[0] == 1:
                    change_values[0] = c.value
                change_objects.append({'name': name,
                                       'interest_rate': c.interest_rate,
                                       'has_interest_below_zero': c.has_interest_below_zero,
                                       'values': change_values,
                                       'range': range(len(dates)),
                                       'account_from': c.account_from,
                                       'account_to': c.account_to})
                
            else:
                add_in_change_object_with_accounts(possible_element, change_objects)
                # add_in_change_object_with_accounts(copy.deepcopy(possible_element), viewing_change_objects)
            
        # This is fine, the problem is that interest change objects are not shown
        
        
        accounts_objects = context['accounts']

        # change_objects
        account_balances3d = []
        for i in range((year+1)*12):
            account_balances2d = all_accounts_balances_for(i, change_objects, account_start_balances, accounts_objects, min_balance=0)
            account_start_balances = account_balances2d[-1]
            account_balances3d.append(account_balances2d)


        balance_objects = []
        for c in change_objects:
            balance_objects.append({'name': c['name'], 'balances': []})

        error_messages = []
        balances = [total_balance]

        if 'threshold' in self.request.GET:
            threshold_balance = self.request.GET['threshold']
            threshold_balance = decimal.Decimal(threshold_balance)
        else:
            threshold_balance = 0

        if len(context['accounts']) == 0 or len(change_objects) == 0:
            context['balances'] = balances
            context['balance_list'] = balance_objects
            context['error_messages'] = error_messages
            return context

        # account_balances2d
        for i in range((year+1)*12):
            # account_balances3d[i]
            (array_balances, errors) = balances_from_balances3d(i, account_balances3d)
            error_messages = error_messages + errors
            for j in range(len(array_balances)):
                balance_objects[j]['balances'].append(array_balances[j])
            balances.append(array_balances[len(array_balances) - 1])

        context['balances'] = balances[-13:-1]
        for balance_object in balance_objects:
            balance_object['balances'] = balance_object['balances'][-12:]
        context['balance_list'] = balance_objects
        context['error_messages'] = error_messages

        viewing_change_objects = copy.deepcopy(change_objects)
        for myObj in viewing_change_objects:
            myObj['values'] = myObj['values'][-12:]
            myObj['range'] = range(len(dates)-12, len(dates))
        context['transaction_list'] = viewing_change_objects
        return context


class FullAllBalanceDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/detail.html'

    def post(self, request):
        transaction_name = request.POST['transactionName']
        if not transaction_name:
            return HttpResponseRedirect(redirect_to=reverse('accounts:full-detail'))
        query = (Q(name=transaction_name) | Q(item__name=transaction_name))
        changes = Transaction.objects.filter(query)
        this_day = datetime.date.today()

        for c in changes:
            if not c.in_month(this_day):
                continue
            if c.recurring:
                c.month_from = month_after_this_date(this_day, c.month_from.day)
                c.save()
                continue
            day_next_month = month_after_this_date(this_day, this_day.day)
            if c.in_month(day_next_month):
                c.month_from = month_after_this_date(this_day, c.month_from.day)
                c.save()
                continue
            c.delete()

        return HttpResponseRedirect(redirect_to=reverse('accounts:full-detail'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year = 0
        if 'year' in self.request.GET:
            year = int(self.request.GET['year'])
        
        context['account'] = {'name': 'All Accounts'}
        user = self.request.user

        accounts = Account.objects.filter(user=user) if user.is_authenticated else []

        account_query = Q()
        total_balance = 0
        context['accounts'] = []
        account_start_balances = []
        for ac in accounts:
            context['accounts'].append(ac)
            total_balance = total_balance + ac.balance
            account_start_balances.append(ac.balance)
            account_query = account_query | (Q(account_from=ac))
        
        account_start_balances.append(total_balance)

        if len(context['accounts']) == 0:
            changes = Transaction.objects.none()
        else:
            changes = Transaction.objects.annotate(
                month_from_day=Extract('month_from', 'day')
            ).filter(account_query).order_by('month_from_day')
        
        dates = months_days_from_day(datetime.date.today(),(year+1)*12)
        context['months'] = month_strings_from_dates(dates[-12:])
        context['year_strings'] = year_strings_from_dates(dates[-12:])
        
        # loop through all the months
        # loop through all change objects
        # for i in range((year+1)*12):
        # keep track of all account balances with every object change as well as total
        # build up output objects

        change_objects = []
        viewing_change_objects = []
        for c in changes:
            if c.item:
                name = c.item.name
            else:
                name = c.name
            possible_element = {'name': name,
                                'values': c.natural_values_for_dates(dates),
                                'range': range(len(dates)),
                                'account_from': c.account_from,
                                'account_to': c.account_to}
            # make a new change object for every interest change
            if c.interest_rate > 0:
                # make new change object
                change_values = c.natural_values_for_dates(dates)
                
                if change_values[0] == 1:
                    change_values[0] = c.value
                change_objects.append({'name': name,
                                       'interest_rate': c.interest_rate,
                                       'has_interest_below_zero': c.has_interest_below_zero,
                                       'values': change_values,
                                       'range': range(len(dates)),
                                       'account_from': c.account_from,
                                       'account_to': c.account_to})
                
            else:
                add_in_change_object_with_accounts(possible_element, change_objects)
                # add_in_change_object_with_accounts(copy.deepcopy(possible_element), viewing_change_objects)
            
        # This is fine, the problem is that interest change objects are not shown
        
        
        accounts_objects = context['accounts']

        # change_objects
        account_balances3d = []
        for i in range((year+1)*12):
            account_balances2d = all_accounts_balances_for(i, change_objects, account_start_balances, accounts_objects, min_balance=0)
            account_start_balances = account_balances2d[-1]
            account_balances3d.append(account_balances2d)

        balance_objects = []
        for c in change_objects:
            balance_objects.append({'name': c['name'], 'balances': []})

        error_messages = []
        balances = [total_balance]

        if 'threshold' in self.request.GET:
            threshold_balance = self.request.GET['threshold']
            threshold_balance = decimal.Decimal(threshold_balance)
        else:
            threshold_balance = 0

        if len(context['accounts']) == 0 or len(change_objects) == 0:
            context['balances'] = balances
            context['balance_list'] = balance_objects
            context['error_messages'] = error_messages
            return context

        for i in range((year+1)*12):
            (array_balances, errors) = balances_from_balances3d(i, account_balances3d)
            error_messages = error_messages + errors
            for j in range(len(array_balances)):
                balance_objects[j]['balances'].append(array_balances[j])
            balances.append(array_balances[len(array_balances) - 1])

        context['balances'] = balances[-13:-1]
        for balance_object in balance_objects:
            balance_object['balances'] = balance_object['balances'][-12:]
        context['balance_list'] = balance_objects
        context['error_messages'] = error_messages

        viewing_change_objects = copy.deepcopy(change_objects)
        for myObj in viewing_change_objects:
            myObj['values'] = myObj['values'][-12:]
            myObj['range'] = range(len(dates)-12, len(dates))
        context['transaction_list'] = viewing_change_objects
        return context


class FullDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/detail.html'

    def post(self, request):
        transaction_name = request.POST['transactionName']
        if not transaction_name:
            return HttpResponseRedirect(redirect_to=reverse('accounts:full-detail'))
        query = (Q(name=transaction_name) | Q(item__name=transaction_name))
        changes = Transaction.objects.filter(query)
        this_day = datetime.date.today()

        for c in changes:
            if not c.in_month(this_day):
                continue
            if c.recurring:
                c.month_from = month_after_this_date(this_day, c.month_from.day)
                c.save()
                continue
            day_next_month = month_after_this_date(this_day, this_day.day)
            if c.in_month(day_next_month):
                c.month_from = month_after_this_date(this_day, c.month_from.day)
                c.save()
                continue
            c.delete()

        return HttpResponseRedirect(redirect_to=reverse('accounts:full-detail'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year = 0
        if 'year' in self.request.GET:
            year = int(self.request.GET['year'])
        
        context['account'] = {'name': 'All Accounts'}
        user = self.request.user

        accounts = Account.objects.filter(user=user) if user.is_authenticated else []

        account_query = Q()
        total_balance = 0
        context['accounts'] = []
        for ac in accounts:
            context['accounts'].append(ac)
            account_query = account_query | (Q(account_from=ac) & Q(account_to=None))
            total_balance = total_balance + ac.balance

        if len(context['accounts']) == 0:
            changes = Transaction.objects.none()
        else:
            changes = Transaction.objects.annotate(
                month_from_day=Extract('month_from', 'day')
            ).filter(account_query).order_by('month_from_day')
        
        dates = months_days_from_day(datetime.date.today(),(year+1)*12)
        context['months'] = month_strings_from_dates(dates[-12:])
        context['year_strings'] = year_strings_from_dates(dates[-12:])
        
        change_objects = []
        viewing_change_objects = []
        for c in changes:
            if c.item:
                name = c.item.name
            else:
                name = c.name

            possible_element = {'name': name, 'values': c.values_for_dates(dates, True), 'range': range(len(dates))}
            add_in_change_object(possible_element, change_objects)
            add_in_change_object(copy.deepcopy(possible_element), viewing_change_objects)

        for myObj in viewing_change_objects:
            myObj['values'] = myObj['values'][-12:]
            myObj['range'] = range(len(dates)-12, len(dates))

        context['transaction_list'] = viewing_change_objects
        
        balance_objects = []
        for c in change_objects:
            balance_objects.append({'name': c['name'], 'balances': []})

        error_messages = []
        balances = [total_balance]

        if 'threshold' in self.request.GET:
            threshold_balance = self.request.GET['threshold']
            threshold_balance = decimal.Decimal(threshold_balance)
        else:
            threshold_balance = 0

        if len(context['accounts']) == 0 or len(change_objects) == 0:
            context['balances'] = balances
            context['balance_list'] = balance_objects
            context['error_messages'] = error_messages
            return context

        for i in range((year+1)*12):
            (array_balances, errors) = balances_for(month=i, change_objects=change_objects, balance_start=balances[i], min_balance=threshold_balance)
            error_messages = error_messages + errors
            for j in range(len(array_balances)):
                balance_objects[j]['balances'].append(array_balances[j])
            balances.append(array_balances[len(array_balances) - 1])
        
        context['balances'] = balances[-13:-1]
        for balance_object in balance_objects:
            balance_object['balances'] = balance_object['balances'][-12:]
        # A balance object looks like this, the balances are for one item:
        """
            {'balances': [Decimal('13061.82'),
                          Decimal('47626.52')],
                   'name': 'MTN Data Sims'}
        """
        context['balance_list'] = balance_objects
        context['error_messages'] = error_messages

        return context


class CredentialForm(forms.ModelForm):
    pin = forms.CharField(required=False)
    password = forms.CharField(widget=widgets.PasswordInput())

    class Meta:
        model = Credential
        fields = ['bank', 'username', 'password', 'pin', 'active']

    @staticmethod
    def get_name():
        return "Credential"

    def clean(self):
        super(CredentialForm, self).clean()

class CredentialCreate(CreateView, LoginRequiredMixin):
    model = Credential
    form_class = CredentialForm

    def get_success_url(self):
        return reverse('accounts:index')

    def form_valid(self, form):
        form.instance.user_id = self.request.user.id
        return super(CredentialCreate, self).form_valid(form)


class CredentialsView(generic.ListView, LoginRequiredMixin):
    template_name = 'accounts/credential_index.html'
    
    def get_queryset(self):
        """Return the current user's credentials"""
        return Credential.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class CredentialUpdate(UpdateView, LoginRequiredMixin):
    model = Credential
    form_class = CredentialForm

    def get_success_url(self):
        return reverse('accounts:credentials')


class CredentialDelete(DeleteView, LoginRequiredMixin):
    model = Credential
    template_name = 'accounts/credential_confirm_delete.html'

    def get_success_url(self):
        return reverse('accounts:credentials')


class TransactionsView(generic.ListView, LoginRequiredMixin):
    template_name = 'accounts/transaction_index.html'
    
    def get_queryset(self):
        """Return the current user's credentials"""
        if 'exact' in self.request.GET:
            exact_query = Q(account_from__credential__user=self.request.user, name=self.request.GET['exact']) | Q(
                account_from__user=self.request.user, name=self.request.GET['exact'])
            return Transaction.objects.filter(exact_query).order_by('name')
        elif 'search' in self.request.GET:
            search_query = Q(account_from__credential__user=self.request.user,
                             name__contains=self.request.GET['search']) | Q(account_from__user=self.request.user,
                                                                            name__contains=self.request.GET['search'])
            return Transaction.objects.filter(search_query).order_by('name')
        query = Q(account_from__credential__user=self.request.user) | Q(account_from__user=self.request.user)
        return Transaction.objects.filter(query).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['name', 'value', 'account_from',
                  'account_to', 'month_from', 'month_to',
                  'recurring', 'increase_multiplier',
                  'increase_month_interval', 'increase_first_interval',
                  'increase_start_date', 'interest_rate',
                  'has_interest_below_zero']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super(TransactionForm, self).__init__(*args, **kwargs)
        query = Q(credential__user=self.user) | Q(user=self.user)
        self.fields['account_from'].queryset = Account.objects.filter(query)
        self.fields['account_to'].queryset = Account.objects.filter(query)

    @staticmethod
    def get_name():
        return "Credential"

    def clean(self):
        super(TransactionForm, self).clean()

class TransactionCreate(CreateView, LoginRequiredMixin):
    model = Transaction
    form_class = TransactionForm

    def get_success_url(self):
        return reverse('accounts:transactions')

    def get_form_kwargs(self):
        kwargs = super(TransactionCreate, self).get_form_kwargs()
        kwargs.update({'user': self.request.user})
        return kwargs

    def form_valid(self, form):
        form.instance.user_id = self.request.user.id
        return super(TransactionCreate, self).form_valid(form)


class TransactionUpdate(UpdateView, LoginRequiredMixin):
    model = Transaction
    form_class = TransactionForm

    def get_form_kwargs(self):
        kwargs = super(TransactionUpdate, self).get_form_kwargs()
        kwargs.update({'user': self.request.user})
        return kwargs

    def get_success_url(self):
        return reverse('accounts:transactions')


class TransactionDelete(DeleteView, LoginRequiredMixin):
    model = Transaction
    template_name = 'accounts/credential_confirm_delete.html'

    def get_success_url(self):
        return reverse('accounts:transactions')


class AccountsView(generic.ListView, LoginRequiredMixin):
    template_name = 'accounts/account_index.html'
    
    def get_queryset(self):
        """Return the current user's accounts"""
        return Account.objects.filter(user=self.request.user).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class AccountForm(forms.ModelForm):

    class Meta:
        model = Account
        fields = ['name', 'credential', 'balance', 'limit', 'account_type', 'account_group']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super(AccountForm, self).__init__(*args, **kwargs)
        self.fields['credential'].queryset = Credential.objects.filter(user=self.user)

    def clean(self):
        super(AccountForm, self).clean()

class AccountCreate(CreateView, LoginRequiredMixin):
    model = Account
    form_class = AccountForm

    def get_success_url(self):
        return reverse('accounts:accounts')

    def get_form_kwargs(self):
        kwargs = super(AccountCreate, self).get_form_kwargs()
        kwargs.update({'user': self.request.user})
        return kwargs

    def form_valid(self, form):
        form.instance.user_id = self.request.user.id
        form.instance.true_balance = form.instance.balance - form.instance.limit
        form.instance.last_updated = datetime.datetime.now()
        return super(AccountCreate, self).form_valid(form)


class AccountUpdate(UpdateView, LoginRequiredMixin):
    model = Account
    form_class = AccountForm

    def get_form_kwargs(self):
        kwargs = super(AccountUpdate, self).get_form_kwargs()
        kwargs.update({'user': self.request.user})
        return kwargs

    def form_valid(self, form):
        form.instance.true_balance = form.instance.balance - form.instance.limit
        form.instance.last_updated = datetime.datetime.now()
        return super(AccountUpdate, self).form_valid(form)

    def get_success_url(self):
        return reverse('accounts:accounts')


class AccountDelete(DeleteView, LoginRequiredMixin):
    model = Account
    template_name = 'accounts/credential_confirm_delete.html'

    def get_success_url(self):
        return reverse('accounts:accounts')
