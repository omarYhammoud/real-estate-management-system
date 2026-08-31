"""
Shared abstract base models. Import these into your app's models instead of
repeating created_at/updated_at boilerplate on every model.

    from apps.core.models import TimeStampedModel

    class Invoice(TimeStampedModel):
        ...
"""
from django.db import models


class TimeStampedModel(models.Model):
    """Adds created_at / updated_at to any model that inherits it."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
