from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    path('properties/', views.PropertyListView.as_view(), name='property_list'),
    # path('properties/<int:pk>/', ..., name='property_detail'),
    # path('units/', ...), path('tenants/', ...), path('contracts/', ...),
]
