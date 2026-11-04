"""
UTrade_app/templatetags/course_tags.py

Gives templates the course / major list:

    {% load course_tags %}
    {% get_course_choices as course_choices %}
    {% for code, label in course_choices %} ... {% endfor %}
"""
from django import template

from ..course_utils import COURSE_CHOICES

register = template.Library()


@register.simple_tag
def get_course_choices():
    """[(code, label), ...] from course_utils.COURSE_CHOICES."""
    return COURSE_CHOICES