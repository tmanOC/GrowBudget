from django.urls import path

from . import views
from .newviews import singleupdate
app_name = 'accounts'
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('<int:pk>/', views.DetailView.as_view(), name='detail'),
    path('v2/<int:pk>/', views.NewDetailView.as_view(), name='new-detail'),
    path('v2/', views.FullDetailView.as_view(), name='full-detail'),
    path('transactional/', views.TransactionalDetailView.as_view(), name='transactional-detail'),
    path('refresh/', views.refresh_accounts, name='refresh'),
    path('credentials/create/', views.CredentialCreate.as_view(), name='credentials-create'),
    path('credentials/', views.CredentialsView.as_view(), name='credentials'),
    path('credentials/<int:pk>/', views.CredentialUpdate.as_view(), name='credentials-update'),
    path('credentials/<int:pk>/delete/', views.CredentialDelete.as_view(), name='credentials-delete'),
    path('credentials/create/', views.CredentialCreate.as_view(), name='credentials-create'),

    path('accounts/', views.AccountsView.as_view(), name='accounts'),
    path('accounts/<int:pk>/', views.AccountUpdate.as_view(), name='account-update'),
    path('accounts/<int:pk>/delete/', views.AccountDelete.as_view(), name='account-delete'),
    path('accounts/create/', views.AccountCreate.as_view(), name='account-create'),


    path('transactions/', views.TransactionsView.as_view(), name='transactions'),
    path('transactions/<int:pk>/', views.TransactionUpdate.as_view(), name='transaction-update'),
    path('transactions/<int:pk>/delete/', views.TransactionDelete.as_view(), name='transaction-delete'),
    path('transactions/create/', views.TransactionCreate.as_view(), name='transaction-create'),

    path('transactions/update-single/', singleupdate.TransactionUpdateSingle.as_view(), name='update-single'),
    # path('', views.IndexView.as_view(), name='index'),
    # path('<int:pk>/', views.DetailView.as_view(), name='detail'),
    # path('<int:pk>/results/', views.ResultsView.as_view(), name='results'),
    # path('<int:question_id>/vote/', views.vote, name='vote'),
]