from django_cron import CronJobBase, Schedule
from accounts.models import Credential, Account
from .fetcher import Fetcher
from decimal import Decimal
import datetime


class FetchCronJob(CronJobBase):
    RUN_EVERY_MINS = 60 * 12  # every 12 hours

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'fetcher.fetch_cron_job'    # a unique code

    def update_accounts(self, credential, fetcher):
        accounts = credential.account_set.all()
        for account in accounts:
            if len(fetcher.balances) < 2:
                continue
            if account.account_type == 'cheque':
                account.balance = Decimal(fetcher.balances[0])
                account.true_balance = account.balance - account.limit
                account.last_updated = datetime.datetime.now()
                account.save()
            elif account.account_type == 'credit':
                account.balance = Decimal(fetcher.balances[1])
                account.true_balance = account.balance - account.limit
                account.last_updated = datetime.datetime.now()
                account.save()

    def do(self):
        """For each active user credential get all their accounts balances
        and set in the account table. Update other tables accordingly if required"""
        credentials = Credential.objects.all()
        for credential in credentials:
            if not credential.active:
                continue
            new_fetcher = Fetcher()
            if credential.bank == 'FNB':
                new_fetcher.login_and_work(credential.username, credential.password, new_fetcher.get_balances)
                self.update_accounts(credential, new_fetcher)
            if credential.bank == 'Nedbank':
                new_fetcher.nedbank_login_and_work(credential.username, credential.password, new_fetcher.nedbank_get_balances)
                self.update_accounts(credential, new_fetcher)
