from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('home/', views.AccountHomeView.as_view(), name='home'),
    path('login/', views.AccountLoginView.as_view(), name='login'),
    path('logout/', views.AccountLogoutView.as_view(), name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),
]
