from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('rent-schedule/', views.RentScheduleListView.as_view(), name='rent_schedule_list'),
    path('rent-schedule/<int:schedule_id>/generate-invoice/', views.GenerateInvoiceView.as_view(), name='generate_invoice'),

    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/create/', views.InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/late-fee/', views.AddLateFeeView.as_view(), name='invoice_add_late_fee'),

    path('payments/record/<int:invoice_id>/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('payments/history/', views.PaymentHistoryView.as_view(), name='payment_history'),

    path('receipts/<int:pk>/', views.ReceiptDetailView.as_view(), name='receipt_detail'),
]
