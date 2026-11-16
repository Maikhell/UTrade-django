from django import template
from django.template import Variable, VariableDoesNotExist
from django.urls import reverse

from UTrade_app.sidebar_menu import SIDEBARS, get_sidebar_role  # noqa: F401

register = template.Library()


def _resolve(context, path):
    try:
        return Variable(path).resolve(context)
    except (VariableDoesNotExist, AttributeError, TypeError):
        return None


@register.inclusion_tag("UTrade_app/partials/_sidebar.html", takes_context=True)
def render_sidebar(context, role, active=""):
    """{% render_sidebar sidebar_role 'dashboard' %}"""
    cfg = SIDEBARS.get(role)
    if not cfg:
        return {"sections": []}

    user = getattr(context.get("request"), "user", None)
    org = context.get("org")
    org_name = (getattr(org, "name", "") or "Organization") if org else ""

    sections = []
    for title, items in cfg["sections"]:
        rows = []
        for it in items:
            badge = None
            if it["badge"]:
                val = _resolve(context, it["badge"])
                if val or it["always"]:
                    badge = {"value": val or 0, "css": it["badge_class"]}
            rows.append({
                "label": it["label"], "icon": it["icon"],
                "url": reverse(it["url"]) if it["url"] else "",
                "active": it["key"] == active, "badge": badge,
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
