"""
Analytics for the *Organization* dashboard.

Produces the same JSON shape as ``dashboard_analytics.build_analytics`` (used by the CBRGU
dashboard) so both dashboards share one front-end, but every number here is scoped to the
querysets of the organization that is logged in.

All scoping is done by the caller (see ``organization_panel`` in the org views), which passes:
    orders_qs     -> _org_order_qs(user)
    preorders_qs  -> _org_preorder_qs(user)
    products_qs   -> _org_product_qs(user)
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from .models import OrderItem, OrganizationPlatformLedger

DEFAULT_PERIOD = "7d"
PERIOD_OPTIONS = [
    {"value": "7d", "label": "Last 7 days"},
    {"value": "1m", "label": "Last 30 days"},
    {"value": "1y", "label": "Last 12 months"},
]
PERIODS = {o["value"]: o["label"] for o in PERIOD_OPTIONS}


# ---------------------------------------------------------------------------
# Platform fee (this organization only)
# ---------------------------------------------------------------------------

def org_platform_fee_summary(org):
    """Accumulated platform fee for ONE organization (never the whole platform)."""
    zero = Decimal("0.00")
    if not org:
        return {"total": zero, "collected": zero, "outstanding": zero,
                "cycles": 0, "overdue": 0, "due_soon": 0}

    ledgers = OrganizationPlatformLedger.objects.filter(organization=org)
    total = ledgers.aggregate(s=Sum("accumulated_fee"))["s"] or zero
    collected = ledgers.filter(status="PAID").aggregate(s=Sum("accumulated_fee"))["s"] or zero
    open_ledgers = ledgers.exclude(status="PAID")
    outstanding = open_ledgers.aggregate(s=Sum("accumulated_fee"))["s"] or zero

    today = timezone.localdate()
    return {
        "total": total,
        "collected": collected,
        "outstanding": outstanding,
        "cycles": ledgers.count(),
        "overdue": open_ledgers.filter(cycle_due__lt=today).count(),
        "due_soon": open_ledgers.filter(
            cycle_due__gte=today, cycle_due__lte=today + timedelta(days=7)
        ).count(),
    }


# ---------------------------------------------------------------------------
# Status grouping
# ---------------------------------------------------------------------------

def _norm(status):
    return (status or "").strip().replace("_", " ").lower()


ORDER_GROUPS = [
    ("Incoming", {"pending", "paid"}),
    ("Accepted", {"accepted"}),
    ("Ready for pickup", {"delivered"}),
    ("Completed", {"completed"}),
    ("Rejected / Cancelled", {"rejected", "cancelled"}),
]
PREORDER_GROUPS = [
    ("Incoming", {"pending"}),
    ("In progress", {"accepted", "approved", "processing", "preparing",
                     "awaiting payment", "waiting stocks", "waiting for stocks"}),
    ("Ready for pickup", {"ready", "ready for pickup"}),
    ("Completed", {"completed"}),
    ("Rejected", {"rejected", "declined"}),
]


def _status_breakdown(qs, groups):
    counts = {label: 0 for label, _ in groups}
    for row in qs.values("status").annotate(n=Count("id")):
        key = _norm(row["status"])
        for label, members in groups:
            if key in members:
                counts[label] += row["n"]
                break
    return {"labels": list(counts.keys()), "data": list(counts.values())}


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

def _period_bounds(period):
    """Return (start_date, end_date, monthly, prev_start, prev_end)."""
    today = timezone.localdate()
    if period == "1y":
        # 12 calendar months ending with the current one
        y, m = today.year, today.month
        m0 = m - 11
        y0 = y
        if m0 <= 0:
            m0 += 12
            y0 -= 1
        start = today.replace(year=y0, month=m0, day=1)
        prev_end = start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        for _ in range(11):  # previous window = the 12 months before `start`
            prev_start = (prev_start - timedelta(days=1)).replace(day=1)
        return start, today, True, prev_start, prev_end

    days = 7 if period == "7d" else 30
    start = today - timedelta(days=days - 1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    return start, today, False, prev_start, prev_end


def _buckets(start, end, monthly):
    out = []
    if monthly:
        cur = start.replace(day=1)
        while cur <= end:
            out.append(cur)
            cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        cur = start
        while cur <= end:
            out.append(cur)
            cur += timedelta(days=1)
    return out


def _key(d, monthly):
    if hasattr(d, "date"):
        d = d.date()
    return (d.year, d.month) if monthly else d


def _label(d, monthly):
    return d.strftime("%b %Y") if monthly else d.strftime("%b %d")


def _series(qs, field, buckets, monthly, agg):
    trunc = TruncMonth if monthly else TruncDate
    rows = qs.annotate(_b=trunc(field)).values("_b").annotate(v=agg).order_by("_b")
    found = {_key(r["_b"], monthly): float(r["v"] or 0) for r in rows if r["_b"]}
    return [found.get(_key(b, monthly), 0) for b in buckets]


def _pct(cur, prev):
    if not prev:
        return None
    return round((cur - prev) / prev * 100, 1)


def _metric(cur, prev):
    return {"value": cur, "previous": prev, "change": _pct(cur, prev)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_analytics(orders_qs, preorders_qs, products_qs, period=DEFAULT_PERIOD):
    if period not in PERIODS:
        period = DEFAULT_PERIOD

    start, end, monthly, p_start, p_end = _period_bounds(period)
    buckets = _buckets(start, end, monthly)

    def in_range(qs, a, b):
        return qs.filter(created_at__date__gte=a, created_at__date__lte=b)

    cur_orders = in_range(orders_qs, start, end)
    prev_orders = in_range(orders_qs, p_start, p_end)
    cur_pre = in_range(preorders_qs, start, end)
    prev_pre = in_range(preorders_qs, p_start, p_end)

    def completed_items(order_qs):
        return OrderItem.objects.filter(
            order__in=order_qs.filter(status__iexact="Completed"),
            product_variant__product__in=products_qs,
        )

    cur_items = completed_items(cur_orders)
    prev_items = completed_items(prev_orders)

    revenue_expr = Sum(F("price") * F("quantity"))
    cur_rev = float(cur_items.aggregate(s=revenue_expr)["s"] or 0)
    prev_rev = float(prev_items.aggregate(s=revenue_expr)["s"] or 0)
    cur_units = int(cur_items.aggregate(s=Sum("quantity"))["s"] or 0)
    prev_units = int(prev_items.aggregate(s=Sum("quantity"))["s"] or 0)
    cur_completed = cur_orders.filter(status__iexact="Completed").count()
    prev_completed = prev_orders.filter(status__iexact="Completed").count()
    cur_aov = round(cur_rev / cur_completed, 2) if cur_completed else 0
    prev_aov = round(prev_rev / prev_completed, 2) if prev_completed else 0

    top = (
        cur_items.values("product_variant__product__name")
        .annotate(units=Sum("quantity"))
        .order_by("-units")[:5]
    )

    return {
        "label": PERIODS[period],
        "labels": [_label(b, monthly) for b in buckets],
        "revenue": _series(cur_items, "order__created_at", buckets, monthly, revenue_expr),
        "orders": _series(cur_orders, "created_at", buckets, monthly, Count("id")),
        "preorders": _series(cur_pre, "created_at", buckets, monthly, Count("id")),
        "orders_status": _status_breakdown(cur_orders, ORDER_GROUPS),
        "preorders_status": _status_breakdown(cur_pre, PREORDER_GROUPS),
        "top_products": {
            "labels": [t["product_variant__product__name"] or "Unknown" for t in top],
            "data": [int(t["units"] or 0) for t in top],
        },
        "summary": {
            "revenue": _metric(cur_rev, prev_rev),
            "orders": _metric(cur_orders.count(), prev_orders.count()),
            "preorders": _metric(cur_pre.count(), prev_pre.count()),
            "units": _metric(cur_units, prev_units),
            "aov": _metric(cur_aov, prev_aov),
        },
    }
