from django.http import HttpResponse
from .fetcher.fetcher import Fetcher
# Create your views here.
from django.conf import settings
PASSWORD = settings.ENV_PASSWORD
USERNAME = settings.ENV_USERNAME


def index(request):
    fetcher = Fetcher()
    fetcher.login_and_work(USERNAME, PASSWORD, fetcher.get_balances)
    return HttpResponse(fetcher.balances)