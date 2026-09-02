"""
URL configuration for Alyousof's Deposits & Operations module.
All routes are prefixed with /operations/ via the root urlconf.
"""
from django.urls import path
from . import views

app_name = 'operations'

urlpatterns = [
    # Security Deposits
    path('security-deposits/', views.SecurityDepositListView.as_view(), name='deposit_list'),
    path('security-deposits/create/', views.SecurityDepositCreateView.as_view(), name='deposit_create'),
    path('security-deposits/<int:pk>/', views.SecurityDepositDetailView.as_view(), name='deposit_detail'),
    path('security-deposits/<int:pk>/edit/', views.SecurityDepositUpdateView.as_view(), name='deposit_edit'),

    # Deductions & Refunds (nested under deposit)
    path('security-deposits/<int:deposit_pk>/deductions/add/', views.DepositDeductionCreateView.as_view(), name='deduction_add'),
    path('security-deposits/<int:deposit_pk>/refunds/add/', views.DepositRefundCreateView.as_view(), name='refund_add'),

    # Maintenance Requests
    path('maintenance/', views.MaintenanceListView.as_view(), name='maintenance_list'),
    path('maintenance/create/', views.MaintenanceCreateView.as_view(), name='maintenance_create'),
    path('maintenance/<int:pk>/', views.MaintenanceDetailView.as_view(), name='maintenance_detail'),
    path('maintenance/<int:pk>/edit/', views.MaintenanceUpdateView.as_view(), name='maintenance_edit'),

    # Expenses
    path('expenses/', views.ExpenseListView.as_view(), name='expense_list'),
    path('expenses/create/', views.ExpenseCreateView.as_view(), name='expense_create'),
    path('expenses/<int:pk>/', views.ExpenseDetailView.as_view(), name='expense_detail'),
    path('expenses/<int:pk>/edit/', views.ExpenseUpdateView.as_view(), name='expense_edit'),
]
