from django.test import TestCase
from .models import Transaction, Credential, Account
from django.contrib.auth import get_user_model
import datetime


class TransactionDateTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='fred', email='email@example.com', password='qwerty')
        self.credential = Credential(user=self.user, bank='FNB', username='', password='')
        self.credential.save()
        self.account_1 = Account(credential=self.credential, name='cheque', account_type='cheque')
        self.account_1.save()

    def tearDown(self):
        self.user = None
        self.credential = None
        self.account_1 = None

    def test_transaction_non_recurring_only_from_date(self):
        transaction = Transaction(account_from=self.account_1, recurring=False, month_from=datetime.date(2018, 8, 1))
        self.assertTrue(transaction.in_month(datetime.date(2018, 8, 12)))
        self.assertFalse(transaction.in_month(datetime.date(2018, 9, 12)))
        self.assertFalse(transaction.in_month(datetime.date(2016, 10, 12)))

    def test_transaction_non_recurring_date_range_same_year(self):
        transaction = Transaction(account_from=self.account_1, recurring=False, month_from=datetime.date(2018, 8, 1),
                                  month_to=datetime.date(2018, 11, 1))
        self.assertTrue(transaction.in_month(datetime.date(2018, 8, 12)))
        self.assertTrue(transaction.in_month(datetime.date(2018, 9, 12)))
        self.assertTrue(transaction.in_month(datetime.date(2018, 11, 12)))
        self.assertFalse(transaction.in_month(datetime.date(2016, 10, 12)))
        self.assertFalse(transaction.in_month(datetime.date(2018, 12, 12)))

    def test_transaction_non_recurring_date_range_more_than_year(self):
        transaction = Transaction(account_from=self.account_1, recurring=False, month_from=datetime.date(2018, 8, 1),
                                  month_to=datetime.date(2019, 11, 1))
        self.assertTrue(transaction.in_month(datetime.date(2018, 8, 12)))
        self.assertTrue(transaction.in_month(datetime.date(2018, 9, 12)))
        self.assertTrue(transaction.in_month(datetime.date(2019, 11, 12)))
        self.assertFalse(transaction.in_month(datetime.date(2016, 10, 12)))
        self.assertFalse(transaction.in_month(datetime.date(2019, 12, 12)))

    def test_transaction_recurring(self):
        transaction = Transaction(account_from=self.account_1, recurring=True, month_from=datetime.date(2018, 8, 1))
        self.assertTrue(transaction.in_month(datetime.date(2018, 8, 12)))
        self.assertTrue(transaction.in_month(datetime.date(2019, 11, 12)))
        self.assertTrue(transaction.in_month(datetime.date(2020, 11, 12)))
        self.assertTrue(transaction.in_month(datetime.date(2018, 9, 12)))

        self.assertFalse(transaction.in_month(datetime.date(2018, 7, 12)))
        self.assertFalse(transaction.in_month(datetime.date(2016, 8, 12)))

    def test_transaction_transferring(self):
        account_2 = Account(credential=self.credential, name='credit', account_type='credit')
        account_2.save()
