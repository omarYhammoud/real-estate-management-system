from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:invoice_pk>/payments/record/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('payments/', views.PaymentHistoryView.as_view(), name='payment_history'),
    path('receipts/<int:pk>/', views.ReceiptDetailView.as_view(), name='receipt_detail'),
]
