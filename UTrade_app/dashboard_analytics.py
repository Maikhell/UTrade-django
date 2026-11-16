"""
Dashboard analytics for a seller / CBRGU account.

build_analytics(user, period) returns everything the dashboard charts need for
one period, as plain JSON-safe data:

    '7d'  last 7 days      one point per day
    '1m'  last 1 month     one point per day (30 days)
    '1y'  last 1 year      one point per month (12 months, including this one)

Days or months with no activity are included as zeros, so the charts always show
a complete, evenly spaced timeline. Each total is also compared with the previous
period of the same length.

Save as UTrade_app/dashboard_analytics.py (next to models.py).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from .models import Order, OrderItem, OrganizationPlatformLedger, PreOrderRequest

DEFAULT_PERIOD = '7d'

PERIODS = {
    '7d': {'label': 'Last 7 days', 'days': 7, 'bucket': 'day', 'fmt': '%a %d'},
    '1m': {'label': 'Last 1 month', 'days': 30, 'bucket': 'day', 'fmt': '%b %d'},
    '1y': {'label': 'Last 1 year', 'days': None, 'bucket': 'month', 'fmt': '%b %Y'},
}
PERIOD_OPTIONS = [
    {'value': '7d', 'label': 'Last 7 Days'},
    {'value': '1m', 'label': 'Last 1 Month'},
    {'value': '1y', 'label': 'Last 1 Year'},
]

# Chart labels -> the (lower-cased) statuses they group
ORDER_BUCKETS = [
    ('Incoming', {'pending', 'paid'}),
    ('In progress', {'accepted', 'processing', 'awaiting payment', 'waiting for stocks'}),
    ('Ready for pickup', {'delivered'}),
    ('Completed', {'completed'}),
    ('Cancelled / rejected', {'cancelled', 'rejected'}),
]
PREORDER_BUCKETS = [
    ('Incoming', {'pending'}),
    ('In progress', {'accepted', 'approved', 'processing', 'preparing', 'awaiting_payment',
                     'awaiting payment', 'waiting_stocks', 'waiting for stocks'}),
    ('Ready for pickup', {'ready', 'ready for pickup'}),
    ('Completed', {'completed'}),
    ('Cancelled / rejected', {'rejected', 'declined', 'cancelled'}),
]

_MONEY = DecimalField(max_digits=14, decimal_places=2)
_LINE_TOTAL = ExpressionWrapper(F('price') * F('quantity'), output_field=_MONEY)


# --------------------------------------------------------------------------- #
# Scope + time windows
# --------------------------------------------------------------------------- #
def seller_scope(user, owner_type=None):
    """(orders, pre-orders) that belong to this seller. Uses a subquery so joins never double-count."""
    order_ids = Order.objects.filter(items__product_variant__product__seller=user).values('id')
    orders = Order.objects.filter(id__in=order_ids)
    pre = PreOrderRequest.objects.filter(seller=user)
    if owner_type:
        pre = pre.filter(product_variant__product__owner_type=owner_type)
    return orders, pre


def _months_back(first_of_month, n):
    m = first_of_month.month - n
    return date(first_of_month.year + (m - 1) // 12, (m - 1) % 12 + 1, 1)


def _window(period):
    """start, end (exclusive), the list of buckets, and the previous window."""
    cfg = PERIODS[period]
    today = timezone.localdate()
    end = today + timedelta(days=1)

    if cfg['bucket'] == 'day':
        n = cfg['days']
        start = today - timedelta(days=n - 1)
        buckets = [start + timedelta(days=i) for i in range(n)]
        prev_start, prev_end = start - timedelta(days=n), start
    else:
        this_month = today.replace(day=1)
        buckets = [_months_back(this_month, i) for i in range(11, -1, -1)]
        start = buckets[0]
        prev_start, prev_end = _months_back(start, 12), start

    return {'start': start, 'end': end, 'buckets': buckets,
            'prev_start': prev_start, 'prev_end': prev_end, 'bucket': cfg['bucket'], 'fmt': cfg['fmt']}


def _key(value, bucket):
    if hasattr(value, 'date'):          # datetime -> date
        value = value.date()
    return value if bucket == 'day' else date(value.year, value.month, 1)


def _series(qs, date_field, bucket, buckets, value):
    trunc = TruncDate(date_field) if bucket == 'day' else TruncMonth(date_field)
    rows = qs.annotate(bkt=trunc).values('bkt').annotate(val=value).order_by('bkt')
    got = {_key(r['bkt'], bucket): (r['val'] or 0) for r in rows}
    return [float(got.get(b, 0)) for b in buckets]


# --------------------------------------------------------------------------- #
# Pieces
# --------------------------------------------------------------------------- #
def _in_range(qs, start, end, field='created_at'):
    return qs.filter(**{f'{field}__date__gte': start, f'{field}__date__lt': end})


def _completed_items(orders, user, start, end):
    done = _in_range(orders, start, end).filter(status__iexact='Completed')
    return OrderItem.objects.filter(order__in=done, product_variant__product__seller=user)


def _status_distribution(qs, groups):
    counts = {}
    for r in qs.values('status').annotate(n=Count('id')).order_by('status'):
        key = (r['status'] or '').strip().lower()
        counts[key] = counts.get(key, 0) + r['n']
    labels, data, used = [], [], set()
    for label, keys in groups:
        labels.append(label)
        data.append(sum(counts.get(k, 0) for k in keys))
        used |= keys
    other = sum(n for k, n in counts.items() if k not in used)
    if other:
        labels.append('Other')
        data.append(other)
    return {'labels': labels, 'data': data}


def _totals(orders, pre, user, start, end):
    items = _completed_items(orders, user, start, end)
    agg = items.aggregate(revenue=Sum(_LINE_TOTAL), units=Sum('quantity'))
    revenue = float(agg['revenue'] or Decimal('0'))
    completed = _in_range(orders, start, end).filter(status__iexact='Completed').count()
    return {
        'revenue': revenue,
        'orders': _in_range(orders, start, end).count(),
        'preorders': _in_range(pre, start, end).count(),
        'units': int(agg['units'] or 0),
        'aov': round(revenue / completed, 2) if completed else 0.0,
    }


def _metric(current, previous):
    change = round((current - previous) / previous * 100, 1) if previous else None
    return {'value': current, 'previous': previous, 'change': change}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def build_analytics(user, period=DEFAULT_PERIOD, owner_type=None):
    if period not in PERIODS:
        period = DEFAULT_PERIOD
    w = _window(period)
    orders, pre = seller_scope(user, owner_type)
    s, e, bucket, buckets = w['start'], w['end'], w['bucket'], w['buckets']

    orders_in = _in_range(orders, s, e)
    pre_in = _in_range(pre, s, e)
    items_in = _completed_items(orders, user, s, e)

    revenue = _series(items_in, 'order__created_at', bucket, buckets, Sum(_LINE_TOTAL))
    orders_series = _series(orders_in, 'created_at', bucket, buckets, Count('id'))
    pre_series = _series(pre_in, 'created_at', bucket, buckets, Count('id'))

    top = (
        items_in.values('product_variant__product__name')
        .annotate(units=Sum('quantity')).order_by('-units')[:5]
    )

    cur = _totals(orders, pre, user, s, e)
    prev = _totals(orders, pre, user, w['prev_start'], w['prev_end'])

    return {
        'period': period,
        'label': PERIODS[period]['label'],
        'bucket': bucket,
        'labels': [b.strftime(w['fmt']) for b in buckets],
        'revenue': revenue,
        'orders': orders_series,
        'preorders': pre_series,
        'orders_status': _status_distribution(orders_in, ORDER_BUCKETS),
        'preorders_status': _status_distribution(pre_in, PREORDER_BUCKETS),
        'top_products': {
            'labels': [r['product_variant__product__name'] or 'Unknown' for r in top],
            'data': [int(r['units'] or 0) for r in top],
        },
        'summary': {k: _metric(cur[k], prev[k]) for k in ('revenue', 'orders', 'preorders', 'units', 'aov')},
    }


def platform_fee_summary():
    """Platform fees across the WHOLE system (every organization, every cycle)."""
    ledgers = OrganizationPlatformLedger.objects.all()
    total = ledgers.aggregate(s=Sum('accumulated_fee'))['s'] or Decimal('0.00')
    collected = ledgers.filter(status=OrganizationPlatformLedger.STATUS_PAID) \
        .aggregate(s=Sum('accumulated_fee'))['s'] or Decimal('0.00')
    open_ledgers = ledgers.exclude(status=OrganizationPlatformLedger.STATUS_PAID)
    today = timezone.localdate()
    return {
        'total': total,
        'collected': collected,
        'outstanding': total - collected,
        'overdue': open_ledgers.filter(cycle_due__lt=today).count(),
        'due_soon': open_ledgers.filter(cycle_due__gte=today, cycle_due__lte=today + timedelta(days=7)).count(),
        'cycles': ledgers.count(),
    }