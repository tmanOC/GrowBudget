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


def refresh_accounts(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse('home'))
    if not request.user.is_staff:
        return HttpResponseRedirect(reverse('accounts:index'))
    job = FetchCronJob()
    job.do()
    return HttpResponseRedirect(reverse('accounts:index'))


def months_days_from_day(today):
    dates = []
    y = today.year
    for x in range(12):
        m = (today.month + x - 1) % 12 + 1
        if m == 1 and x != 0:
            y += 1
        d = 1
        dates.append(datetime.date(y, m, d))
    return dates


def month_strings_from_dates(dates):
    return list(map(lambda x: x.strftime('%b'), dates))


def balances_for(month, change_objects, balance_start, min_balance=0):
    balance = balance_start
    balances = []
    error_messages = []
    for j in range(len(change_objects)):  # the range of change_objects
        balance += decimal.Decimal(change_objects[j]['values'][month])
        balances.append(balance)
        if balance < min_balance:
            error_messages.append('negative balance ' + str(balance) + ' at ' + change_objects[j]['name'] + ' ' + str(month))
    return balances, error_messages


class IndexView(generic.ListView, LoginRequiredMixin):
    # model = get_user_model()
    template_name = 'accounts/index.html'
    context_object_name = 'accounts_list'

    def get_queryset(self):
        """Return the accounts for this user's credentials"""
        user = self.request.user
        print(user.id)
        print(user.username)
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

        # Add in two lists of changes
        # Let's make an array of months for the top row of the table
        dates = months_days_from_day(datetime.date.today())
        context['months'] = month_strings_from_dates(dates)
        # Next fetch all changes/transactions related to this account
        account = context['object']
        changes = account.get_related_transactions()

        # Setup simple change objects
        change_objects = []
        for c in changes:
            change_objects.append({'name': c.name, 'values': c.values_for_dates(dates, c.account_from_id == account.id)})

        context['transaction_list'] = change_objects

        # balances, balance list and error messages
        balance_objects = []
        for c in change_objects:
            balance_objects.append({'name': c['name'], 'balances': []})

        error_messages = []
        balances = [account.balance]

        for i in range(12):  # the range of months
            (array_balances, errors) = balances_for(month=i, change_objects=change_objects, balance_start=balances[i])
            error_messages = error_messages + errors
            for j in range(len(array_balances)):  # the range of change_objects
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

        # Add in two lists of changes
        # Let's make an array of months for the top row of the table
        dates = months_days_from_day(datetime.date.today())
        context['months'] = month_strings_from_dates(dates)
        # Next fetch all changes/transactions related to this account
        account = context['object']
        changes = account.get_related_transactions()

        # Setup simple change objects
        change_objects = []
        for c in changes:
            if c.item:
                name = c.item.name
            else:
                name = c.name

            possible_element = {'name': name, 'values': c.values_for_dates(dates, c.account_from_id == account.id)}

            add_in_change_object(possible_element, change_objects)

        context['transaction_list'] = change_objects

        # balances, balance list and error messages
        balance_objects = []
        for c in change_objects:
            balance_objects.append({'name': c['name'], 'balances': []})

        error_messages = []
        balances = [account.balance]

        for i in range(12):  # the range of months
            (array_balances, errors) = balances_for(month=i, change_objects=change_objects, balance_start=balances[i])
            error_messages = error_messages + errors
            for j in range(len(array_balances)):  # the range of change_objects
                balance_objects[j]['balances'].append(array_balances[j])
            balances.append(array_balances[len(array_balances) - 1])

        context['balances'] = balances
        context['balance_list'] = balance_objects
        context['error_messages'] = error_messages
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
        # Add in two lists of changes
        # Let's make an array of months for the top row of the table
        dates = months_days_from_day(datetime.date.today())
        context['months'] = month_strings_from_dates(dates)

        # Setup simple change objects
        change_objects = []
        for c in changes:
            if c.item:
                name = c.item.name
            else:
                name = c.name

            possible_element = {'name': name, 'values': c.values_for_dates(dates, True), 'range': range(len(dates))}
            add_in_change_object(possible_element, change_objects)

        context['transaction_list'] = change_objects
        # balances, balance list and error messages
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

        for i in range(12):  # the range of months
            (array_balances, errors) = balances_for(month=i, change_objects=change_objects, balance_start=balances[i], min_balance=threshold_balance)
            error_messages = error_messages + errors
            for j in range(len(array_balances)):  # the range of change_objects
                balance_objects[j]['balances'].append(array_balances[j])
            balances.append(array_balances[len(array_balances) - 1])


        context['balances'] = balances[0:-1]
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


# Credentials views
class CredentialCreate(CreateView, LoginRequiredMixin):
    model = Credential
    form_class = CredentialForm

    def get_success_url(self):
        return reverse('accounts:index')

    def form_valid(self, form):
        form.instance.user_id = self.request.user.id
        return super(CredentialCreate, self).form_valid(form)


class CredentialsView(generic.ListView, LoginRequiredMixin):
    # model = get_user_model()
    template_name = 'accounts/credential_index.html'
    # context_object_name = 'accounts_list'

    # bank and active
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
    # model = get_user_model()
    template_name = 'accounts/transaction_index.html'
    # context_object_name = 'accounts_list'

    # bank and active
    def get_queryset(self):
        """Return the current user's credentials"""
        print(self.request.GET)


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
    # pin = forms.CharField(required=False)
    # password = forms.CharField(widget=widgets.PasswordInput())

    class Meta:
        model = Transaction
        fields = ['name', 'value', 'account_from', 'account_to', 'month_from', 'month_to', 'recurring']

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


# Credentials views
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
    # model = get_user_model()
    template_name = 'accounts/account_index.html'
    # context_object_name = 'accounts_list'

    # bank and active
    def get_queryset(self):
        """Return the current user's accounts"""
        print(self.request.GET)
        return Account.objects.filter(user=self.request.user).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class AccountForm(forms.ModelForm):
    # pin = forms.CharField(required=False)
    # password = forms.CharField(widget=widgets.PasswordInput())

    class Meta:
        model = Account
        fields = ['name', 'credential', 'balance', 'limit', 'account_type']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super(AccountForm, self).__init__(*args, **kwargs)
        self.fields['credential'].queryset = Credential.objects.filter(user=self.user)

    def clean(self):
        super(AccountForm, self).clean()


# Credentials views
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
