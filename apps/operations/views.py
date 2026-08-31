"""
Alyousof: build views for Security Deposits, Deposit Details, Refunds,
Deductions, Maintenance, Maintenance Details, Expenses, Create Expense here.
"""
from django.views.generic import ListView
from .models import MaintenanceRequest


class MaintenanceListView(ListView):
    model = MaintenanceRequest
    template_name = 'operations/maintenance_list.html'
    context_object_name = 'requests'
