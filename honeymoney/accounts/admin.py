from django.contrib import admin
from .models import Account, Transaction, Item


admin.site.register(Account)
admin.site.register(Transaction)
admin.site.register(Item)
