from django.views.generic.base import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from ..models import Transaction, month_after_this_date, month_before_this_date
from ..views import months_days_from_day
from django.db.models import Q
from django.urls import reverse
import datetime


def move_change_by_month(c, this_day):
    if not c.in_month(this_day):
        return
    if c.recurring:
        c.month_from = month_after_this_date(this_day, c.month_from.day)
        c.save()
        return
    day_next_month = month_after_this_date(this_day, this_day.day)
    if c.in_month(day_next_month):
        c.month_from = month_after_this_date(this_day, c.month_from.day)
        c.save()
        return
    c.delete()

class TransactionUpdateSingle(TemplateView, LoginRequiredMixin):
    template_name = 'accounts/transaction_update_single.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transaction_name'] = self.request.GET['exact']
        context['date_index'] = self.request.GET['date-index']
        return context

    def post(self, request):
        transaction_name = request.POST['transactionName']
        if not transaction_name:
            return HttpResponseRedirect(redirect_to=reverse('accounts:full-detail'))
        query = (Q(name=transaction_name) | Q(item__name=transaction_name))
        changes = list(Transaction.objects.filter(query))
        print(changes)
        this_day = datetime.date.today()
        month_index = int(request.POST['dateIndex'])
        value = float(request.POST['value'])

        if value != 0:
            new_change = changes[0].create_simple_transaction(value, month_index)
            new_change.save()
        if month_index == 0:
            for c in changes:
                move_change_by_month(c ,this_day)

            return HttpResponseRedirect(redirect_to=reverse('accounts:full-detail'))

        month_to_change = months_days_from_day(this_day)[month_index]
        new_transactions = []
        for c in changes:
            if not c.in_month(month_to_change):
                continue
            if c.recurring and not c.in_month(month_before_this_date(month_to_change, month_to_change.day)):
                # beginning of recurring
                c.month_from = month_after_this_date(c.month_from, c.month_from.day)
                c.save()
                continue
            if c.recurring:
                # middle of recurring
                new_transactions.append(c.create_new_with_month_after_end(month_to_change))
                c.month_from = month_after_this_date(month_to_change, c.month_from.day)
                c.save()
                continue
            if not c.in_month(month_before_this_date(month_to_change, month_to_change.day)) and not c.in_month(month_after_this_date(month_to_change, month_to_change.day)):
                # month_from = month_to
                c.delete()
                continue
            if not c.in_month(month_before_this_date(month_to_change, month_to_change.day)):
                # beginning of non_recurring
                c.month_from = month_after_this_date(c.month_from, c.month_from.day)
                c.save()
                continue
            if not c.in_month(month_after_this_date(month_to_change, month_to_change.day)):
                # end of non-recurring
                c.month_to = month_before_this_date(c.month_to, c.month_to.day)
                c.save()
                continue
            new_transactions.append(c.create_new_with_month_after_end(month_to_change))
            c.month_from = month_after_this_date(month_to_change, c.month_from.day)
            c.save()
            # middle of non-recurring
        for transaction in new_transactions:
            transaction.save()
        return HttpResponseRedirect(redirect_to=reverse('accounts:full-detail'))
