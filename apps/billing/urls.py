from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    # path('invoices/create/', ..., name='invoice_create'),
    # path('payments/record/', ..., name='payment_create'),
    # path('payments/history/', ..., name='payment_history'),
    # path('receipts/<int:pk>/', ..., name='receipt_detail'),
]
