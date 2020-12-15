from django.test import TestCase
from .fetcher.fetch_job import FetchCronJob
from users.models import CustomUser
from accounts.models import Account, Credential
from honeymoney.env import USERNAME, PASSWORD

from .fetcher.fetcher import Fetcher
# Create your tests here.


class FetcherTest(TestCase):
    def mock_balances(self, cron_job, credential, balances):
        class HasBalance:
            def __init__(self):
                self.balances = ['0', '0']
        mock_fetcher = HasBalance()
        mock_fetcher.balances = balances  # just something that has balances is required
        cron_job.update_accounts(credential, mock_fetcher)

    def test_account_update(self):
        user = CustomUser.objects.create_user(username='fred', email='email@example.com', password='qwerty')
        credential = Credential(user=user, bank='FNB', username=USERNAME, password=PASSWORD)
        credential.save()
        account_1 = Account(credential=credential, name='cheque', account_type='cheque')
        account_1.save()
        account_2 = Account(credential=credential, name='credit', account_type='credit', limit=20000)
        account_2.save()
        cron_job = FetchCronJob()

        # cron_job.do() for a real test
        # mock steps for speed
        self.mock_balances(cron_job, credential, ['1000', '1000'])

        self.assertQuerysetEqual(
            Account.objects.order_by('id'),
            ['<Account: cheque 1000.00>', '<Account: credit -19000.00>']
        )