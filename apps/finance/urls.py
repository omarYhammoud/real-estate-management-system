from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    # path('reports/profit-loss/', ..., name='report_profit_loss'),
    # path('reports/revenue-summary/', ..., name='report_revenue_summary'),
    # path('reports/expense-summary/', ..., name='report_expense_summary'),
    # path('reports/outstanding-receivables/', ..., name='report_outstanding'),
]
