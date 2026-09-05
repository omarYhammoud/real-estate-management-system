"""
Shared view mixins — role-based access helpers used across every app's
class-based views.

    from apps.core.mixins import RoleRequiredMixin

    class InvoiceListView(RoleRequiredMixin, ListView):
        allowed_roles = ['admin', 'accountant']
        ...
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a view to users whose `.role` is in `allowed_roles`."""
    allowed_roles = ()

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or user.role in self.allowed_roles
        )

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()
