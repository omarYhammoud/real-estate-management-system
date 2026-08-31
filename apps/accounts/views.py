from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import CreateView
from django.urls import reverse_lazy
from .forms import UserRegistrationForm


class AccountLoginView(LoginView):
    template_name = 'accounts/login.html'


class AccountLogoutView(LogoutView):
    next_page = 'accounts:login'


class RegisterView(CreateView):
    form_class = UserRegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:login')
