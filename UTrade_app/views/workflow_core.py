"""
One engine for the Orders and Pre-Orders boards of Management AND organizations.

  Incoming -> Accepted -> Processing / Awaiting Payment / Waiting for Stocks
           -> Ready for Pickup -> Completed        (or Rejected)

Each caller passes a Scope that says which records it may see and touch, who
notifications come from, and which sidebar to show.
"""
import json
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_date

from ..models import ChatMessage, Conversation, Order, OrderItem, PreOrderRequest
from ..utils import accrue_platform_fee_for_order, is_allowed_email, log_action, send_email

logger = logging.getLogger(__name__)

TEMPLATE = 'UTrade_app/management/management_orders/workflow.html'
ROW_LIMIT = 50      # rows (and detail dialogs) rendered per tab
MAX_BATCH = 20

STEPS = ['Requested', 'Accepted', 'In progress', 'Ready for pickup', 'Completed']

# key, label, icon
TABS = [
    ('incoming', 'Incoming', 'bi-inbox'),
    ('accepted', 'Accepted', 'bi-check2-all'),
    ('processing', 'Processing', 'bi-gear'),
    ('awaiting', 'Awaiting Payment', 'bi-wallet2'),
    ('stocks', 'Waiting for Stocks', 'bi-box-seam'),
    ('ready', 'Ready for Pickup', 'bi-bag-check'),
    ('completed', 'Completed', 'bi-clipboard-check'),
    ('rejected', 'Rejected', 'bi-x-octagon'),
]
TAB_LABEL = {key: label for key, label, _ in TABS}
MID_KEYS = ('accepted', 'processing', 'awaiting', 'stocks')
SELECTABLE_KEYS = ('incoming',) + MID_KEYS + ('ready',)
STEP_OF = {
    'incoming': 1, 'accepted': 2, 'processing': 3, 'awaiting': 3,
    'stocks': 3, 'ready': 4, 'completed': 6, 'rejected': 0,
}

# Statuses (as stored in the database) that belong to each tab
ORDER_STATUSES = {
    'incoming': ['Pending', 'Paid'],
    'accepted': ['Accepted'],
    'processing': ['Processing'],
    'awaiting': ['Awaiting Payment'],
    'stocks': ['Waiting for Stocks'],
    'ready': ['Delivered'],
    'completed': ['Completed'],
    'rejected': ['Rejected'],
}
PREORDER_STATUSES = {
    'incoming': ['PENDING', 'Pending', 'pending'],
    'accepted': ['ACCEPTED', 'APPROVED', 'Accepted', 'Approved'],
    'processing': ['PROCESSING', 'PREPARING', 'Processing', 'Preparing'],
    'awaiting': ['AWAITING_PAYMENT', 'Awaiting Payment'],
    'stocks': ['WAITING_STOCKS', 'Waiting for Stocks'],
    'ready': ['READY', 'Ready', 'Ready for Pickup'],
    'completed': ['COMPLETED', 'Completed'],
    'rejected': ['REJECTED', 'DECLINED', 'Rejected', 'Declined'],
}
# The value written when an action moves a record into a tab
NEW_STATUS = {
    'order': {
        'accepted': 'Accepted', 'processing': 'Processing',
        'awaiting': 'Awaiting Payment', 'stocks': 'Waiting for Stocks',
        'ready': 'Delivered', 'completed': 'Completed', 'rejected': 'Rejected',
    },
    'preorder': {
        'accepted': 'ACCEPTED', 'processing': 'PROCESSING',
        'awaiting': 'AWAITING_PAYMENT', 'stocks': 'WAITING_STOCKS',
        'ready': 'READY', 'completed': 'COMPLETED', 'rejected': 'REJECTED',
    },
}


class Scope:
    """
    Who is looking at the board.

    key            'management' or 'organization' (picks the sidebar)
    order_qs       callable -> Order queryset this user may see and touch
    preorder_qs    callable -> PreOrderRequest queryset this user may see and touch
    urls           {'order': (page_url_name, batch_url_name), 'preorder': (...)}
    titles         {'order': '...', 'preorder': '...'}
    actor_label    shown in notifications ("" for management, the org name otherwise)
    extra_context  callable -> dict merged into the template context
    line_filter    optional callable(OrderItem) -> bool, hides items that are not theirs
    accrue_fees    record the 3% platform fee when an order is completed
    """

    def __init__(self, key, order_qs, preorder_qs, urls, titles, actor_label='',
                 extra_context=None, line_filter=None, accrue_fees=False):
        self.key = key
        self.order_qs = order_qs
        self.preorder_qs = preorder_qs
        self.urls = urls
        self.titles = titles
        self.actor_label = actor_label
        self.extra_context = extra_context or (lambda: {})
        self.line_filter = line_filter
        self.accrue_fees = accrue_fees


def _statuses(kind):
    return ORDER_STATUSES if kind == 'order' else PREORDER_STATUSES


def _status_key(kind, status):
    for key, values in _statuses(kind).items():
        if status in values:
            return key
    return 'other'


def _image_url(product):
    if not product:
        return ''
    try:
        if getattr(product, 'image', None):
            return product.image.url
    except ValueError:
        pass
    images = list(product.images.all())
    if images:
        try:
            return images[0].image.url
        except ValueError:
            return ''
    return ''


# ---------------------------------------------------------------------------
# Normalise an Order / PreOrderRequest so one template can render both
# ---------------------------------------------------------------------------
def _decorate_common(obj, kind, key):
    obj.wf_kind = kind
    obj.wf_key = key
    obj.wf_label = TAB_LABEL.get(key, obj.status)
    obj.wf_mid = key in MID_KEYS
    obj.wf_step = STEP_OF.get(key, 0)
    obj.wf_in_flight = 1 <= obj.wf_step <= len(STEPS)
    return obj


def _decorate_order(o, scope):
    lines, kept_total, hidden = [], Decimal('0'), 0
    for item in o.items.all():
        if scope.line_filter and not scope.line_filter(item):
            hidden += 1      # an item that belongs to another seller
            continue
        variant = item.product_variant
        product = variant.product if variant else None
        lines.append({
            'name': product.name if product else 'Deleted product',
            'variant': variant.variant_name if variant else '',
            'qty': item.quantity,
            'price': item.price,
            'total': item.get_cost(),
            'image': _image_url(product),
        })
        kept_total += item.get_cost()

    buyer = o.user
    _decorate_common(o, 'order', _status_key('order', o.status))
    o.wf_ref = o.order_number or f'#{o.id}'
    o.wf_buyer = buyer
    o.wf_buyer_name = buyer.get_full_name() or buyer.username
    o.wf_buyer_no = buyer.student_no
    o.wf_course = buyer.course or ''
    o.wf_section = buyer.section or ''
    o.wf_org = buyer.org_acronym
    o.wf_lines = lines
    o.wf_qty = sum(line['qty'] for line in lines)
    o.wf_amount = kept_total if (hidden and lines) else o.total_amount
    o.wf_est = o.estimated_pickup
    o.wf_payment = o.get_payment_method_display()
    o.wf_location = o.pickup_location or o.meetup_location or ''
    o.wf_reason = o.rejection_reason
    o.wf_reason_note = o.rejection_note
    o.wf_buyer_note = o.buyer_note
    o.wf_seller_note = o.seller_note
    o.wf_paid = o.status == 'Paid'
    return o


def _decorate_preorder(po):
    variant = po.product_variant
    product = variant.product if variant else None
    buyer = po.buyer
    line = {
        'name': product.name if product else 'Deleted product',
        'variant': variant.variant_name if variant else '',
        'qty': po.quantity,
        'price': variant.price if variant else 0,
        'total': po.get_total_price(),
        'image': _image_url(product),
    }
    _decorate_common(po, 'preorder', _status_key('preorder', po.status))
    po.wf_ref = f'#{po.id}'
    po.wf_buyer = buyer
    po.wf_buyer_name = po.full_name_at_time or buyer.get_full_name() or buyer.username
    po.wf_buyer_no = po.student_no_at_time or buyer.student_no
    po.wf_course = po.course_at_time or buyer.course or ''
    po.wf_section = po.section_at_time or buyer.section or ''
    po.wf_org = po.course_at_time or buyer.org_acronym
    po.wf_lines = [line]
    po.wf_qty = po.quantity
    po.wf_amount = po.get_total_price()
    po.wf_est = po.estimated_pickup
    po.wf_payment = 'Cash on Pickup'
    po.wf_location = (product.meetup_location_text if product else '') or ''
    po.wf_reason = po.rejection_reason
    po.wf_reason_note = po.rejection_note
    po.wf_buyer_note = ''
    po.wf_seller_note = po.seller_note
    po.wf_paid = False
    return po


# ---------------------------------------------------------------------------
# Board (list page)
# ---------------------------------------------------------------------------
def _base_queryset(kind, scope):
    if kind == 'order':
        return (
            scope.order_qs()
            .select_related('user', 'user__org_link', 'seller')
            .prefetch_related(
                Prefetch(
                    'items',
                    queryset=OrderItem.objects
                    .select_related('product_variant__product__seller')
                    .prefetch_related('product_variant__product__images'),
                )
            )
            .order_by('-created_at')
        )
    return (
        scope.preorder_qs()
        .select_related(
            'buyer', 'buyer__org_link', 'seller',
            'product_variant', 'product_variant__product',
        )
        .prefetch_related('product_variant__product__images')
        .order_by('-created_at')
    )


def _apply_filters(kind, qs, search, date_from, date_to, org_filter):
    if search:
        if kind == 'order':
            qs = qs.filter(
                Q(id__icontains=search)
                | Q(order_number__icontains=search)
                | Q(user__username__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__display_name__icontains=search)
                | Q(user__student_no__icontains=search)
            )
        else:
            qs = qs.filter(
                Q(id__icontains=search)
                | Q(buyer__username__icontains=search)
                | Q(buyer__first_name__icontains=search)
                | Q(buyer__last_name__icontains=search)
                | Q(buyer__student_no__icontains=search)
                | Q(product_variant__product__name__icontains=search)
                | Q(full_name_at_time__icontains=search)
            )

    if date_from:
        d = parse_date(date_from)
        if d:
            qs = qs.filter(created_at__date__gte=d)
    if date_to:
        d = parse_date(date_to)
        if d:
            qs = qs.filter(created_at__date__lte=d)

    if org_filter:
        if kind == 'order':
            qs = qs.filter(
                Q(user__course__iexact=org_filter)
                | Q(user__org_link__course_code__iexact=org_filter)
                | Q(user__org_link__name__iexact=org_filter)
            )
        else:
            qs = qs.filter(
                Q(buyer__course__iexact=org_filter)
                | Q(buyer__org_link__course_code__iexact=org_filter)
                | Q(course_at_time__iexact=org_filter)
            )
    return qs


def _org_options(kind, base):
    base = base.order_by()      # ordering would defeat DISTINCT on the values below
    if kind == 'order':
        values = (
            list(base.values_list('user__course', flat=True).distinct())
            + list(base.values_list('user__org_link__course_code', flat=True).distinct())
        )
    else:
        values = (
            list(base.values_list('buyer__course', flat=True).distinct())
            + list(base.values_list('course_at_time', flat=True).distinct())
            + list(base.values_list('buyer__org_link__course_code', flat=True).distinct())
        )
    return sorted(set(filter(None, values)))


def _board_context(request, kind, scope):
    search = request.GET.get('search', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    org_filter = request.GET.get('organization', '').strip()

    base = _base_queryset(kind, scope)
    qs = _apply_filters(kind, base, search, date_from, date_to, org_filter)
    statuses = _statuses(kind)
    if kind == 'order':
        def decorate(row):
            return _decorate_order(row, scope)
    else:
        decorate = _decorate_preorder

    tabs, all_rows, counts = [], [], {}
    for key, label, icon in TABS:
        tab_qs = qs.filter(status__in=statuses[key])
        rows = [decorate(r) for r in tab_qs[:ROW_LIMIT]]
        counts[key] = tab_qs.count()
        tabs.append({
            'key': key,
            'label': label,
            'icon': icon,
            'rows': rows,
            'count': counts[key],
            'mid': key in MID_KEYS,
            'selectable': key in SELECTABLE_KEYS,
        })
        all_rows.extend(rows)

    is_order = kind == 'order'
    page_name, batch_name = scope.urls[kind]
    context = {
        'scope': scope.key,
        'kind': kind,
        'noun': 'order' if is_order else 'pre-order',
        'noun_plural': 'orders' if is_order else 'pre-orders',
        'title': scope.titles[kind],
        'subtitle': (
            'Incoming → Accepted → Processing / Payment / Stocks → Ready for Pickup → Completed'
        ),
        'page_url': reverse(page_name),
        'batch_url': reverse(batch_name),
        'tabs': tabs,
        'all_rows': all_rows,
        'steps': STEPS,
        'stats': {
            'incoming': counts['incoming'],
            'in_progress': sum(counts[k] for k in MID_KEYS),
            'ready': counts['ready'],
            'completed': counts['completed'],
        },
        'total': qs.count(),
        'incoming_count': counts['incoming'],
        'completed_count': counts['completed'],
        'org_options': _org_options(kind, base),
        'row_limit': ROW_LIMIT,
        'current_filters': {
            'search': search,
            'date_from': date_from,
            'date_to': date_to,
            'organization': org_filter,
        },
    }
    context.update(scope.extra_context())
    return context


def board(request, kind, scope):
    return render(request, TEMPLATE, _board_context(request, kind, scope))


# ---------------------------------------------------------------------------
# Notifications (chat + email) to the buyer
# ---------------------------------------------------------------------------
def _ref(kind, obj):
    if kind == 'order':
        return obj.order_number or f'#{obj.id}'
    return f'#{obj.id}'


def _first_product(kind, obj):
    try:
        if kind == 'order':
            item = obj.items.select_related('product_variant__product').first()
            if item and item.product_variant:
                return item.product_variant.product
            return None
        return obj.product_variant.product if obj.product_variant_id else None
    except Exception:
        return None


def _chat_buyer(actor, buyer, product, text):
    conversation, _ = Conversation.objects.get_or_create(
        product=product, buyer=buyer, seller=actor,
    )
    ChatMessage.objects.create(
        conversation=conversation, user=actor, content=text, is_read=False,
    )


def _notify_seller_chat(actor, order, text):
    """A system note to the order's seller account when the order is rejected."""
    product = _first_product('order', order)
    conversation, _ = Conversation.objects.get_or_create(
        product=product, buyer=actor, seller=order.seller,
    )
    ChatMessage.objects.create(
        conversation=conversation, user=actor, content=text, is_read=False,
    )


def _email_buyer(kind, obj, buyer, action, reason, note, est, scope):
    email = (getattr(buyer, 'email', '') or '').strip().lower()
    if not is_allowed_email(email):
        return

    noun = 'Order' if kind == 'order' else 'Pre-Order'
    ref = _ref(kind, obj)
    name = buyer.get_full_name() or buyer.username
    by = f' by {scope.actor_label}' if scope.actor_label else ''
    if kind == 'order':
        total = obj.total_amount
        names = [
            i.product_variant.product.name
            for i in obj.items.select_related('product_variant__product')
            if i.product_variant and i.product_variant.product
        ]
        what = ', '.join(names) or 'your items'
    else:
        total = obj.get_total_price()
        product = _first_product(kind, obj)
        what = product.name if product else 'your item'

    if action == 'accept':
        subject = f'UTrade – {noun} {ref} Accepted'
        body = (
            f'Hi {name},\n\n'
            f'Your {noun.lower()} {ref} for {what} (₱{total}) has been accepted{by}.\n'
            f'Estimated ready for pickup: {est or "to be confirmed"}.\n\n'
            f'You will be notified when it is ready.\n\nThank you for using UTrade.'
        )
    elif action == 'ready':
        subject = f'UTrade – {noun} {ref} Ready for Pickup'
        body = (
            f'Hi {name},\n\n'
            f'Your {noun.lower()} {ref} for {what} (₱{total}) is ready for pickup.\n'
            f'Please proceed to the designated meetup location.\n\nThank you for using UTrade.'
        )
    elif action == 'reject':
        subject = f'UTrade – {noun} {ref} Rejected'
        detail = (reason or 'Not specified') + (f' – {note}' if note else '')
        body = (
            f'Hi {name},\n\n'
            f'Unfortunately your {noun.lower()} {ref} (₱{total}) was rejected{by}.\n'
            f'Reason: {detail}\n\n'
            f'You may place a new {noun.lower()} or reach out for clarification.\n\n'
            f'Thank you for using UTrade.'
        )
    else:
        return

    send_email(email, subject, body)


def _notify(kind, actor, obj, action, reason, note, estimated, scope):
    if action not in ('accept', 'ready', 'reject'):
        return
    buyer = obj.user if kind == 'order' else obj.buyer
    noun = 'order' if kind == 'order' else 'pre-order'
    ref = _ref(kind, obj)
    est = estimated or obj.estimated_pickup or 'to be confirmed'
    label = f' ({scope.actor_label})' if scope.actor_label else ''

    if action == 'accept':
        text = (
            f'✅ SYSTEM{label}: Your {noun} {ref} has been accepted.\n'
            f'Estimated ready for pickup: {est}.'
        )
    elif action == 'ready':
        text = (
            f'📦 SYSTEM{label}: Your {noun} {ref} is ready for pickup.\n'
            f'Please proceed to the designated meetup location.'
        )
    else:
        text = (
            f'🚨 SYSTEM{label}: Your {noun} {ref} was rejected.\n'
            f'Reason: {reason}' + (f' — {note}' if note else '')
        )

    try:
        _chat_buyer(actor, buyer, _first_product(kind, obj), text)
    except Exception:
        logger.exception('Buyer chat notification failed for %s %s', kind, obj.id)

    try:
        _email_buyer(kind, obj, buyer, action, reason, note, est, scope)
    except Exception:
        logger.exception('Buyer email failed for %s %s', kind, obj.id)

    # Orders: also tell the seller account about a rejection (unless it IS the actor)
    if kind == 'order' and action == 'reject' and obj.seller_id and obj.seller_id != actor.id:
        try:
            _notify_seller_chat(
                actor, obj,
                f'🚨 SYSTEM ({scope.actor_label or "Management"}): Order {ref} from '
                f'{buyer.get_full_name() or buyer.username} was rejected.\n'
                f'Reason: {reason}\nAmount: ₱{obj.total_amount}',
            )
        except Exception:
            logger.exception('Seller chat notification failed for order %s', obj.id)


# ---------------------------------------------------------------------------
# Batch / single status updates (same rules for orders and pre-orders)
# ---------------------------------------------------------------------------
def _rules(kind):
    statuses = _statuses(kind)
    new = NEW_STATUS[kind]
    mid = sum((statuses[k] for k in MID_KEYS), [])
    return {
        'accept': (new['accepted'], statuses['incoming']),
        'reject': (new['rejected'], statuses['incoming']),
        'processing': (new['processing'], mid),
        'awaiting_payment': (new['awaiting'], mid),
        'waiting_stocks': (new['stocks'], mid),
        'ready': (new['ready'], mid),
        'complete': (new['completed'], statuses['ready']),
        'set_estimate': (None, mid + statuses['ready']),   # status unchanged
    }


def batch(request, kind, scope):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

    noun = 'order' if kind == 'order' else 'pre-order'
    action = (data.get('action') or '').strip().lower()
    raw_ids = data.get('order_ids') or data.get('preorder_ids') or []
    reason = (data.get('reason') or '').strip()
    note = (data.get('note') or '').strip()
    estimated = (data.get('estimated_pickup') or '').strip()

    if not isinstance(raw_ids, list) or not raw_ids:
        return JsonResponse({'success': False, 'message': f'No {noun}s selected'}, status=400)
    if len(raw_ids) > MAX_BATCH:
        return JsonResponse(
            {'success': False, 'message': f'Maximum {MAX_BATCH} {noun}s per batch'}, status=400
        )
    ids = [int(i) for i in raw_ids if str(i).isdigit()]

    rules = _rules(kind)
    if action not in rules:
        return JsonResponse({'success': False, 'message': 'Invalid action'}, status=400)
    new_status, from_statuses = rules[action]

    if action == 'reject' and not reason:
        return JsonResponse({'success': False, 'message': 'Rejection reason required'}, status=400)
    if action == 'set_estimate' and not estimated:
        return JsonResponse({'success': False, 'message': 'Estimated pickup required'}, status=400)

    model = Order if kind == 'order' else PreOrderRequest
    scoped = scope.order_qs() if kind == 'order' else scope.preorder_qs()

    # 1) Work out which records this user may change. Scoped querysets can use
    #    DISTINCT and outer joins, and PostgreSQL refuses SELECT ... FOR UPDATE on
    #    those. That was why accepting organization orders silently failed.
    target_ids = list(
        scoped.filter(id__in=ids, status__in=from_statuses)
        .order_by()
        .values_list('id', flat=True)
        .distinct()
    )

    # 2) Lock exactly those rows with a plain query (and re-check their status).
    locked = model.objects.filter(id__in=target_ids, status__in=from_statuses).order_by('id')
    if kind == 'order':
        locked = locked.select_related('user')
    else:
        locked = locked.select_related('buyer', 'product_variant__product')

    updated = 0
    to_notify = []
    with transaction.atomic():
        for obj in locked.select_for_update(of=('self',)):
            if action == 'set_estimate':
                obj.estimated_pickup = estimated[:50]
                obj.save(update_fields=['estimated_pickup', 'updated_at'])
            else:
                obj.status = new_status
                fields = ['status', 'updated_at']
                if action == 'reject':
                    obj.rejection_reason = reason[:100]
                    fields.append('rejection_reason')
                    if reason == 'Other' and note:
                        obj.rejection_note = note[:500]
                        fields.append('rejection_note')
                elif estimated:
                    obj.estimated_pickup = estimated[:50]
                    fields.append('estimated_pickup')
                obj.save(update_fields=fields)
                to_notify.append(obj)

            updated += 1
            label = 'Order' if kind == 'order' else 'PreOrder'
            log_action(
                user=request.user,
                action=f'{label} {action.title()}',
                item_type=label,
                item_name=f'{label} #{obj.id}',
                details=(
                    f'Status → {new_status or obj.status}'
                    + (f'; reason={reason}' if reason else '')
                    + (f'; estimate={estimated}' if estimated else '')
                ),
            )

            # Organization orders: record the 3% platform fee on completion
            # (safe to repeat: it skips orders that already have a fee line)
            if action == 'complete' and kind == 'order' and scope.accrue_fees:
                try:
                    accrue_platform_fee_for_order(obj)
                except Exception:
                    logger.exception('Platform fee accrual failed for order %s', obj.id)

    # Send notifications only after the database changes are committed
    for obj in to_notify:
        _notify(kind, request.user, obj, action, reason, note, estimated, scope)

    if updated == 0:
        return JsonResponse({
            'success': False,
            'message': f'No matching {noun}s updated (wrong status or already processed).',
        })
    return JsonResponse({
        'success': True,
        'message': f'{updated} {noun}(s) updated.',
        'updated': updated,
    })