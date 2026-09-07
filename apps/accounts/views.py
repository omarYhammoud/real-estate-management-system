from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import resolve_url
from django.views.generic import CreateView, TemplateView
from django.urls import reverse_lazy
from .forms import UserRegistrationForm
from .models import User


class AccountLoginView(LoginView):
    template_name = 'accounts/login.html'

    def get_default_redirect_url(self):
        if self.request.user.role == User.Role.TENANT:
            return resolve_url('accounts:home')
        return resolve_url(settings.LOGIN_REDIRECT_URL)


class AccountLogoutView(LogoutView):
    next_page = 'accounts:login'


class AccountHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/home.html'


class RegisterView(CreateView):
    form_class = UserRegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:login')
