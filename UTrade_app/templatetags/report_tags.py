from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()

_URLS = {
    "orders": "reports.orders",
    "preorders": "reports.preorders",
    "products": "reports.products",
    "users": "reports.users",
}


def _url(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return ""


@register.inclusion_tag("UTrade_app/reports/_report_modal.html", takes_context=True)
def report_modal(context):
    """Renders the shared 'Generate Report' modal (#reportModal) for head and organization users."""
    from ..views.reports import report_options, ORDER_SORTS, PREORDER_SORTS, PRODUCT_SORTS, USER_SORTS

    request = context.get("request")
    opts = report_options(request) if request is not None else None
    return {
        "opts": opts,
        "urls": {k: _url(v) for k, v in _URLS.items()},
        "order_sorts": [(k, v[1]) for k, v in ORDER_SORTS.items()],
        "preorder_sorts": [(k, v[1]) for k, v in PREORDER_SORTS.items()],
        "product_sorts": [(k, v[1]) for k, v in PRODUCT_SORTS.items()],
        "user_sorts": [(k, v[1]) for k, v in USER_SORTS.items()],
    }
