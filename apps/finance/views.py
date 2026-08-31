"""
Chaheen: build the Dashboard (KPIs) and the report views here (Profit & Loss,
Revenue Summary, Expense Summary, Outstanding Receivables, Payment Report,
Transaction Report, Tenant Statement, Property Financial Performance).
Restrict each view to the correct roles using apps.core.mixins.RoleRequiredMixin.
"""
from django.views.generic import TemplateView
from apps.core.mixins import RoleRequiredMixin


class DashboardView(RoleRequiredMixin, TemplateView):
    template_name = 'finance/dashboard.html'
    allowed_roles = ['admin', 'property_manager', 'accountant', 'owner']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # TODO: total properties, total units, occupancy rate, active
        # contracts, rent due, collected rent, outstanding rent, expenses,
        # revenue, profit/loss.
        return context
