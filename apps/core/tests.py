from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import path
from django.views import View

from .mixins import RoleRequiredMixin


User = get_user_model()


class AllowedView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.ACCOUNTANT,)

    def get(self, request):
        return HttpResponse('allowed')


class EmptyRolesView(RoleRequiredMixin, View):
    def get(self, request):
        return HttpResponse('allowed')


urlpatterns = [
    path('allowed/', AllowedView.as_view()),
    path('empty-roles/', EmptyRolesView.as_view()),
]


@override_settings(ROOT_URLCONF=__name__, LOGIN_URL='/accounts/login/')
class RoleRequiredMixinTests(TestCase):
    def create_user(self, username, role=User.Role.TENANT, **kwargs):
        return User.objects.create_user(
            username=username,
            password='test-password',
            role=role,
            **kwargs,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get('/allowed/')

        self.assertRedirects(
            response,
            '/accounts/login/?next=/allowed/',
            fetch_redirect_response=False,
        )

    def test_allowed_role_can_access_view(self):
        self.client.force_login(
            self.create_user('accountant', User.Role.ACCOUNTANT)
        )

        self.assertEqual(self.client.get('/allowed/').status_code, 200)

    def test_disallowed_authenticated_role_receives_403(self):
        self.client.force_login(self.create_user('tenant'))

        self.assertEqual(self.client.get('/allowed/').status_code, 403)

    def test_superuser_bypasses_role_restriction(self):
        self.client.force_login(
            self.create_user('superuser', is_staff=True, is_superuser=True)
        )

        self.assertEqual(self.client.get('/allowed/').status_code, 200)

    def test_empty_allowed_roles_denies_normal_user(self):
        self.client.force_login(self.create_user('ordinary-user'))

        self.assertEqual(self.client.get('/empty-roles/').status_code, 403)
