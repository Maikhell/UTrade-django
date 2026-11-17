from django import template
from django.template import Variable, VariableDoesNotExist
from django.urls import reverse

from UTrade_app.sidebar_menu import SIDEBARS, get_sidebar_role  # noqa: F401
from UTrade_app.sidebar_counts import get_sidebar_counts

register = template.Library()


def _resolve(context, path):
    try:
        return Variable(path).resolve(context)
    except (VariableDoesNotExist, AttributeError, TypeError):
        return None


def _counts(context):
    """Computed once per request, then reused by the sidebar and the dashboard card."""
    request = context.get("request")
    user = getattr(request, "user", None)
    cached = getattr(request, "_sidebar_counts", None)
    if cached is None:
        cached = get_sidebar_counts(user, context.get("org"))
        if request is not None:
            request._sidebar_counts = cached
    return cached


@register.simple_tag(takes_context=True)
def dashboard_alert_count(context):
    """{% dashboard_alert_count as dash_alert %}"""
    return _counts(context)["alert_total"]


@register.inclusion_tag("UTrade_app/partials/_sidebar.html", takes_context=True)
def render_sidebar(context, role, active=""):
    """{% render_sidebar sidebar_role 'dashboard' %}"""
    user = getattr(context.get("request"), "user", None)
    org = context.get("org")
    role = role or get_sidebar_role(user, org)
    cfg = SIDEBARS.get(role)
    if not cfg:
        return {"sections": []}
    org_name = (getattr(org, "name", "") or "Organization") if org else ""
    counts = _counts(context)

    def value(path):
        return counts[path] if path in counts else _resolve(context, path)

    sections = []
    for title, items in cfg["sections"]:
        rows = []
        for it in items:
            badge = None
            if it["badge"]:
                val = value(it["badge"])
                if val or it["always"]:
                    badge = {"value": val or 0, "css": it["badge_class"]}
            rows.append({
                "label": it["label"], "icon": it["icon"],
                "url": reverse(it["url"]) if it["url"] else "",
                "active": it["key"] == active, "badge": badge,
                "alert": bool(it.get("alert") and value(it["alert"])),
            })
        sections.append({"title": title, "items": rows})

    name = ""
    if user is not None:
        name = user.get_full_name() or user.get_short_name()
    return {
        "sections": sections,
        "brand_title": cfg["title"].format(org=org_name),
        "brand_sub": name,
        "add_product_url": reverse("product.create") if cfg["add_product"] else "",
    }