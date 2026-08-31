"""
Custom template filters/tags shared across apps.
Usage in a template: {% load core_extras %}
"""
from django import template

register = template.Library()


@register.filter
def currency(value):
    """{{ invoice.total_amount|currency }} -> $1,250.00"""
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return value
