"""
Professional PDF reports for CBRGU Head and Organization accounts.

Place this file in your app's ``views/`` package (next to the organization views module).

Scope rules
-----------
* CBRGU Head (user_role in management / cbrgu_staff): platform-wide, optional course + section filters.
* Organization: only students whose course matches the organization's course/program
  (``org.course_code``), optionally narrowed to one section (e.g. 4-1, 3-1). Course cannot be
  overridden from the request. Organizations with no ``course_code`` (e.g. CSG) are not
  course-restricted but still only see their own orders / pre-orders / products.

Setup: set ORG_VIEWS_MODULE to the module that defines ``is_organization``, ``_require_org``,
``_org_product_qs``, ``_org_order_qs`` and ``_org_preorder_qs``.
"""
import importlib
import re
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from ..course_utils import VALID_COURSE_CODES, course_matches
from ..models import Order, PreOrderRequest, Product

# >>> EDIT THIS if your organization views live in a differently named module <<<
ORG_VIEWS_MODULE = "organization_views"

HEAD_ROLES = ("management", "cbrgu_staff")
ROW_CAP = 1000

ORDER_STATUSES = ["Pending", "Paid", "Accepted", "Delivered", "Completed", "Rejected", "Cancelled"]
PREORDER_STATUSES = ["Pending", "Accepted", "Ready for pickup", "Completed", "Rejected"]
PRODUCT_STATUSES = ["Approved", "Pending", "Unlisted", "Rejected"]

ORDER_SORTS = {
    "newest": ("-created_at", "Newest first"),
    "oldest": ("created_at", "Oldest first"),
    "amount_desc": ("-total_amount", "Amount: high to low"),
    "amount_asc": ("total_amount", "Amount: low to high"),
    "status": ("status", "Status (A-Z)"),
    "buyer": ("user__last_name", "Buyer name (A-Z)"),
}
PREORDER_SORTS = {
    "newest": ("-created_at", "Newest first"),
    "oldest": ("created_at", "Oldest first"),
    "pickup": ("estimated_pickup", "Pickup date"),
    "status": ("status", "Status (A-Z)"),
    "buyer": ("buyer__last_name", "Buyer name (A-Z)"),
}
PRODUCT_SORTS = {
    "name": ("name", "Name (A-Z)"),
    "newest": ("-id", "Newest first"),
    "oldest": ("id", "Oldest first"),
    "category": ("category", "Category"),
    "status": ("status", "Status (A-Z)"),
}
USER_SORTS = {
    "name": ("last_name", "Last name (A-Z)"),
    "course": ("course", "Course"),
    "section": ("section", "Section"),
    "newest": ("-id", "Newest first"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _org_module():
    return importlib.import_module(f"{__package__}.{ORG_VIEWS_MODULE}")


def _scope(request):
    """Return ('head'|'org', org_or_None, org_module_or_None) or None if not allowed."""
    user = request.user
    if getattr(user, "user_role", None) in HEAD_ROLES:
        return "head", None, None
    mod = _org_module()
    if mod.is_organization(user):
        return "org", mod._require_org(user), mod
    return None


def money(value):
    try:
        return "PHP {:,.2f}".format(Decimal(value or 0))
    except Exception:
        return "PHP 0.00"


def _full_name(u):
    if not u:
        return "-"
    return (u.get_full_name() or getattr(u, "username", "") or "-").strip()


def _class_label(u):
    course = (getattr(u, "course", "") or "").strip()
    section = (getattr(u, "section", "") or "").strip()
    return (f"{course} {section}".strip()) or "-"


def _parse_date(value):
    from datetime import datetime
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _status_q(qs, status):
    """Case/underscore tolerant status filter."""
    if not status:
        return qs
    pattern = "^" + re.escape(status).replace(r"\ ", "[ _]").replace(" ", "[ _]") + "$"
    return qs.filter(status__iregex=pattern)


def _student_filter(qs, prefix, kind, org, course, section):
    """Limit a queryset to students of a course/section. `prefix` is 'user__' or 'buyer__'."""
    code = (getattr(org, "course_code", "") or "") if kind == "org" else (course or "")
    if code:
        found = qs.order_by().values_list(prefix + "course", flat=True).distinct()
        matching = {c for c in found if c and course_matches(c, code)}
        qs = qs.filter(**{prefix + "course__in": matching})
    if section:
        qs = qs.filter(**{prefix + "section__iexact": section})
    return qs, code


def _scope_label(kind, org, code, section):
    if kind == "head":
        parts = ["CBRGU - Platform-wide"]
        if code:
            parts.append(code)
        if section:
            parts.append(f"Section {section}")
        return " | ".join(parts)
    name = getattr(org, "name", "Organization")
    cls = f"{code} {section}".strip() if code else ""
    return f"{name}" + (f" | {cls}" if cls else "")


def _pdf_response(template, context, filename):
    html = render_to_string(template, context)
    buf = BytesIO()
    result = pisa.CreatePDF(html, dest=buf, encoding="utf-8")
    if result.err:
        return HttpResponse("Could not generate the PDF report.", status=500)
    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp


def _base_context(request, kind, org, title, scope_label, filters, summary, extra=None):
    ctx = {
        "title": title,
        "scope_label": scope_label,
        "is_head": kind == "head",
        "org_name": getattr(org, "name", ""),
        "generated_at": timezone.localtime().strftime("%B %d, %Y %I:%M %p"),
        "generated_by": _full_name(request.user),
        "filters": [(k, v) for k, v in filters if v],
        "summary": summary,
        "cap": ROW_CAP,
    }
    ctx.update(extra or {})
    return ctx


def report_options(request):
    """Data for the report modal (course/section choices for this user's scope)."""
    sc = _scope(request)
    if not sc:
        return None
    kind, org, _ = sc
    User = get_user_model()
    students = User.objects.exclude(section__isnull=True).exclude(section="")
    if kind == "org":
        code = getattr(org, "course_code", "") or ""
        courses = [code] if code else []
        if code:
            found = students.order_by().values_list("course", flat=True).distinct()
            ok = {c for c in found if c and course_matches(c, code)}
            students = students.filter(course__in=ok)
    else:
        courses = sorted(VALID_COURSE_CODES)
    sections = sorted({s.strip() for s in students.order_by().values_list("section", flat=True).distinct() if s and s.strip()})
    return {
        "kind": kind,
        "courses": courses,
        "sections": sections,
        "order_statuses": ORDER_STATUSES,
        "preorder_statuses": PREORDER_STATUSES,
        "product_statuses": PRODUCT_STATUSES,
        "org_label": (f"{getattr(org, 'name', '')} - {getattr(org, 'course_code', '') or 'all students'}" if kind == "org" else "Entire platform"),
    }


def _guard(request):
    sc = _scope(request)
    if not sc:
        return None, HttpResponseForbidden("You do not have access to reports.")
    return sc, None


def _pick(request, sorts, default):
    key = request.GET.get("sort", default)
    return key if key in sorts else default


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@login_required
def orders_report(request):
    sc, err = _guard(request)
    if err:
        return err
    kind, org, mod = sc
    g = request.GET

    qs = Order.objects.all() if kind == "head" else mod._org_order_qs(request.user)
    qs = qs.select_related("user").prefetch_related("items__product_variant__product")

    qs, code = _student_filter(qs, "user__", kind, org, g.get("course"), g.get("section", "").strip())
    status = g.get("status", "").strip()
    qs = _status_q(qs, status)
    d_from, d_to = _parse_date(g.get("date_from")), _parse_date(g.get("date_to"))
    if d_from:
        qs = qs.filter(created_at__date__gte=d_from)
    if d_to:
        qs = qs.filter(created_at__date__lte=d_to)

    sort_key = _pick(request, ORDER_SORTS, "newest")
    qs = qs.order_by(ORDER_SORTS[sort_key][0], "-id")

    total_count = qs.count()
    agg = qs.aggregate(total=Sum("total_amount"))
    completed = qs.filter(status__iexact="Completed")
    comp_agg = completed.aggregate(total=Sum("total_amount"), n=Count("id"))

    rows = []
    for o in qs[:ROW_CAP]:
        items = ", ".join(
            f"{i.product_variant.product.name} x{i.quantity}"
            for i in o.items.all() if i.product_variant_id
        ) or "-"
        rows.append({
            "number": getattr(o, "order_number", None) or f"#{o.id}",
            "date": timezone.localtime(o.created_at).strftime("%b %d, %Y"),
            "buyer": _full_name(o.user),
            "class": _class_label(o.user),
            "items": items,
            "total": money(o.total_amount),
            "status": o.status,
        })

    status_counts = [(r["status"], r["n"]) for r in qs.order_by().values("status").annotate(n=Count("id")).order_by("status")]
    summary = [
        ("Total orders", total_count),
        ("Total amount", money(agg["total"])),
        ("Completed orders", comp_agg["n"] or 0),
        ("Completed amount", money(comp_agg["total"])),
    ]
    filters = [
        ("Status", status),
        ("From", d_from.strftime("%b %d, %Y") if d_from else ""),
        ("To", d_to.strftime("%b %d, %Y") if d_to else ""),
        ("Section", g.get("section", "").strip()),
        ("Sort", ORDER_SORTS[sort_key][1]),
    ]
    ctx = _base_context(request, kind, org, "Orders Report",
                        _scope_label(kind, org, code, g.get("section", "").strip()),
                        filters, summary,
                        {"rows": rows, "status_counts": status_counts, "truncated": total_count > ROW_CAP,
                         "total_count": total_count})
    return _pdf_response("UTrade_app/reports/pdf/orders.html", ctx,
                         f"orders_report_{timezone.localdate():%Y%m%d}.pdf")


# ---------------------------------------------------------------------------
# Pre-orders
# ---------------------------------------------------------------------------

@login_required
def preorders_report(request):
    sc, err = _guard(request)
    if err:
        return err
    kind, org, mod = sc
    g = request.GET

    qs = PreOrderRequest.objects.all() if kind == "head" else mod._org_preorder_qs(request.user)
    qs = qs.select_related("buyer", "product_variant__product")

    qs, code = _student_filter(qs, "buyer__", kind, org, g.get("course"), g.get("section", "").strip())
    status = g.get("status", "").strip()
    qs = _status_q(qs, status)
    d_from, d_to = _parse_date(g.get("date_from")), _parse_date(g.get("date_to"))
    if d_from:
        qs = qs.filter(created_at__date__gte=d_from)
    if d_to:
        qs = qs.filter(created_at__date__lte=d_to)

    sort_key = _pick(request, PREORDER_SORTS, "newest")
    qs = qs.order_by(PREORDER_SORTS[sort_key][0], "-id")

    total_count = qs.count()
    rows, grand = [], Decimal("0.00")
    for p in qs[:ROW_CAP]:
        try:
            amount = p.get_total_price()
        except Exception:
            amount = Decimal("0.00")
        grand += Decimal(amount or 0)
        pickup = p.estimated_pickup
        rows.append({
            "id": f"#{p.id}",
            "date": timezone.localtime(p.created_at).strftime("%b %d, %Y"),
            "buyer": (getattr(p, "full_name_at_time", "") or _full_name(p.buyer)),
            "class": (f"{getattr(p, 'course_at_time', '') or ''} {getattr(p.buyer, 'section', '') or ''}".strip() or "-"),
            "product": p.product_variant.product.name if p.product_variant_id else "-",
            "qty": p.quantity,
            "pickup": pickup.strftime("%b %d, %Y") if pickup else "-",
            "total": money(amount),
            "status": str(p.status).replace("_", " ").title(),
        })

    status_counts = [(str(r["status"]).replace("_", " ").title(), r["n"])
                     for r in qs.order_by().values("status").annotate(n=Count("id")).order_by("status")]
    summary = [
        ("Total pre-orders", total_count),
        ("Total units", qs.aggregate(u=Sum("quantity"))["u"] or 0),
        ("Total value" + (" (first %d)" % ROW_CAP if total_count > ROW_CAP else ""), money(grand)),
    ]
    filters = [
        ("Status", status),
        ("From", d_from.strftime("%b %d, %Y") if d_from else ""),
        ("To", d_to.strftime("%b %d, %Y") if d_to else ""),
        ("Section", g.get("section", "").strip()),
        ("Sort", PREORDER_SORTS[sort_key][1]),
    ]
    ctx = _base_context(request, kind, org, "Pre-Orders Report",
                        _scope_label(kind, org, code, g.get("section", "").strip()),
                        filters, summary,
                        {"rows": rows, "status_counts": status_counts, "truncated": total_count > ROW_CAP,
                         "total_count": total_count})
    return _pdf_response("UTrade_app/reports/pdf/preorders.html", ctx,
                         f"preorders_report_{timezone.localdate():%Y%m%d}.pdf")


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@login_required
def products_report(request):
    sc, err = _guard(request)
    if err:
        return err
    kind, org, mod = sc
    g = request.GET

    qs = Product.objects.all() if kind == "head" else mod._org_product_qs(request.user)
    qs = qs.select_related("seller")
    status = g.get("status", "").strip()
    if status:
        qs = qs.filter(status__iexact=status)
    category = g.get("category", "").strip()
    if category:
        qs = qs.filter(category__iexact=category)

    sort_key = _pick(request, PRODUCT_SORTS, "name")
    qs = qs.order_by(PRODUCT_SORTS[sort_key][0], "id")

    total_count = qs.count()
    rows, units = [], 0
    for p in qs[:ROW_CAP]:
        try:
            stock = p.get_total_stock()
        except Exception:
            stock = 0
        try:
            price = p.get_price_range()
        except Exception:
            price = "-"
        units += stock or 0
        rows.append({
            "name": p.name,
            "code": getattr(p, "product_code", "") or "-",
            "category": getattr(p, "category", "") or "-",
            "seller": _full_name(p.seller) if p.seller_id else "-",
            "price": price,
            "stock": stock,
            "preorder": "Yes" if getattr(p, "pre_order", False) else "No",
            "status": p.status,
        })

    status_counts = [(r["status"], r["n"]) for r in qs.order_by().values("status").annotate(n=Count("id")).order_by("status")]
    summary = [("Total products", total_count), ("Units in stock" + (" (first %d)" % ROW_CAP if total_count > ROW_CAP else ""), units)]
    filters = [("Status", status), ("Category", category), ("Sort", PRODUCT_SORTS[sort_key][1])]
    ctx = _base_context(request, kind, org, "Products Report",
                        _scope_label(kind, org, "", ""), filters, summary,
                        {"rows": rows, "status_counts": status_counts, "truncated": total_count > ROW_CAP,
                         "total_count": total_count})
    return _pdf_response("UTrade_app/reports/pdf/products.html", ctx,
                         f"products_report_{timezone.localdate():%Y%m%d}.pdf")


# ---------------------------------------------------------------------------
# Students / users  (replaces the old generate_pdf_orgs)
# ---------------------------------------------------------------------------

@login_required
def users_report(request):
    sc, err = _guard(request)
    if err:
        return err
    kind, org, _ = sc
    g = request.GET
    User = get_user_model()

    qs = User.objects.filter(user_role="student") if hasattr(User, "user_role") else User.objects.all()
    qs, code = _student_filter(qs, "", kind, org, g.get("course"), g.get("section", "").strip())
    if g.get("status"):
        qs = qs.filter(status__iexact=g["status"].strip())

    sort_key = _pick(request, USER_SORTS, "name")
    qs = qs.order_by(USER_SORTS[sort_key][0], "id")

    total_count = qs.count()
    rows = [{
        "name": _full_name(u),
        "student_no": getattr(u, "student_no", "") or "-",
        "course": getattr(u, "course", "") or "-",
        "section": getattr(u, "section", "") or "-",
        "email": u.email or "-",
        "status": getattr(u, "status", "") or "-",
    } for u in qs[:ROW_CAP]]

    summary = [("Total students", total_count)]
    filters = [("Section", g.get("section", "").strip()), ("Status", g.get("status", "").strip()),
               ("Sort", USER_SORTS[sort_key][1])]
    ctx = _base_context(request, kind, org, "Students Report",
                        _scope_label(kind, org, code, g.get("section", "").strip()), filters, summary,
                        {"rows": rows, "truncated": total_count > ROW_CAP, "total_count": total_count})
    return _pdf_response("UTrade_app/reports/pdf/users.html", ctx,
                         f"students_report_{timezone.localdate():%Y%m%d}.pdf")


# Backwards-compatible name for the old view: point the old URL at the new report.
generate_pdf_orgs = users_report
