from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('finance/reports/', views.ReportIndexView.as_view(), name='reports'),
    path('finance/reports/profit-loss/', views.ProfitLossReportView.as_view(), name='report_profit_loss'),
    path('finance/reports/revenue/', views.RevenueSummaryView.as_view(), name='report_revenue'),
    path('finance/reports/expenses/', views.ExpenseSummaryView.as_view(), name='report_expenses'),
    path('finance/reports/receivables/', views.OutstandingReceivablesView.as_view(), name='report_receivables'),
    path('finance/reports/payments/', views.PaymentReportView.as_view(), name='report_payments'),
    path('finance/reports/transactions/', views.TransactionReportView.as_view(), name='report_transactions'),
    path('finance/reports/tenant-statement/', views.TenantStatementView.as_view(), name='report_tenant_statement'),
    path('finance/reports/property-performance/', views.PropertyPerformanceView.as_view(), name='report_property_performance'),
]
