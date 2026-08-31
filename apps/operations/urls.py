from django.urls import path
from . import views

app_name = 'operations'

urlpatterns = [
    path('maintenance/', views.MaintenanceListView.as_view(), name='maintenance_list'),
    # path('deposits/', ...), path('deposits/<int:pk>/', ...),
    # path('expenses/', ...), path('expenses/create/', ...),
]
