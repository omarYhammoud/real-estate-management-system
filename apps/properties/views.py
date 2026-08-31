"""
Omar: build CRUD views here (Owners, Properties, Units, Tenants, Contracts).
Suggested pattern: Django generic class-based views (ListView, DetailView,
CreateView, UpdateView, DeleteView) — one per model, mirroring urls.py.
"""
from django.views.generic import ListView
from .models import Property


class PropertyListView(ListView):
    model = Property
    template_name = 'properties/property_list.html'
    context_object_name = 'properties'
