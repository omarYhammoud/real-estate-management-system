from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import UserRegistrationForm


User = get_user_model()


class UserRegistrationFormTests(TestCase):
    def valid_form_data(self, **overrides):
        data = {
            'username': 'newtenant',
            'email': 'tenant@example.com',
            'first_name': 'New',
            'last_name': 'Tenant',
            'password1': 'A-secure-password-123!',
            'password2': 'A-secure-password-123!',
        }
        data.update(overrides)
        return data

    def test_registration_form_does_not_expose_role(self):
        self.assertNotIn('role', UserRegistrationForm().fields)

    def test_registered_user_is_tenant_with_hashed_password(self):
        password = self.valid_form_data()['password1']
        form = UserRegistrationForm(data=self.valid_form_data(role=User.Role.ADMIN))

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        self.assertEqual(user.role, User.Role.TENANT)
        self.assertNotEqual(user.password, password)
        self.assertTrue(user.check_password(password))

    def test_invalid_registration_does_not_create_user(self):
        response = self.client.post(
            reverse('accounts:register'),
            self.valid_form_data(password2='different-password'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The two password fields didn’t match.')
        self.assertFalse(User.objects.filter(username='newtenant').exists())


class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.password = 'A-secure-password-123!'
        self.user = User.objects.create_user(
            username='accountant',
            password=self.password,
            role=User.Role.ACCOUNTANT,
        )

    def test_login_with_valid_credentials_uses_configured_redirect(self):
        response = self.client.post(
            reverse('accounts:login'),
            {'username': self.user.username, 'password': self.password},
        )

        self.assertRedirects(
            response,
            reverse('finance:dashboard'),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            int(self.client.session['_auth_user_id']),
            self.user.pk,
        )

    def test_invalid_credentials_do_not_authenticate(self):
        response = self.client.post(
            reverse('accounts:login'),
            {'username': self.user.username, 'password': 'wrong-password'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_external_next_url_is_not_used(self):
        response = self.client.post(
            f"{reverse('accounts:login')}?next=https://example.com/unsafe",
            {'username': self.user.username, 'password': self.password},
        )

        self.assertRedirects(
            response,
            reverse('finance:dashboard'),
            fetch_redirect_response=False,
        )

    def test_logout_ends_session_and_redirects_to_login(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('accounts:logout'))

        self.assertRedirects(response, reverse('accounts:login'))
        self.assertNotIn('_auth_user_id', self.client.session)
