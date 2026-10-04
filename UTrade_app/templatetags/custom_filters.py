from django import template

register = template.Library()

@register.filter(name='abs')
def absolute_value(value):
    try:
        return abs(value)
    except (TypeError, ValueError):
        return value