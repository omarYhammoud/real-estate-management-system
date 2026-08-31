from django.contrib import admin
from .models import SecurityDeposit, DepositDeduction, DepositRefund, MaintenanceRequest, Expense

admin.site.register(SecurityDeposit)
admin.site.register(DepositDeduction)
admin.site.register(DepositRefund)
admin.site.register(MaintenanceRequest)
admin.site.register(Expense)
