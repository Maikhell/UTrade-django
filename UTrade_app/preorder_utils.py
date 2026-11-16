"""Pre-order rules shared by add-to-cart, cart, checkout and the cancel / reject code."""
from django.db.models import F
from django.db.models.functions import Least
from django.utils import timezone

# A pre-order variation with "No limit" keeps this number in `stocks`, so pages that
# only look at stock never treat it as sold out.
NO_LIMIT_STOCK = 99999
RELEASED_STATUSES = ('REJECTED', 'DECLINED', 'CANCELLED')


def fmt_dt(value):
    if not value:
        return ''
    return timezone.localtime(value).strftime('%b %d, %Y %I:%M %p').replace(' 0', ' ')


def order_gate(product):
    """'ok', 'out' (regular, no stock), or 'upcoming' / 'closed' / 'full' (pre-order)."""
    if product.pre_order:
        state = product.preorder_window_state
        if state in ('upcoming', 'closed'):
            return state
        return 'full' if product.preorder_remaining_total == 0 else 'ok'
    return 'ok' if product.get_total_stock > 0 else 'out'


def preorder_block_reason(product, variant, quantity=1, already_in_cart=0):
    """Why this pre-order line can't be added / placed right now, or None."""
    state = product.preorder_window_state
    if state == 'upcoming':
        return f'Pre-orders for "{product.name}" open on {fmt_dt(product.preorder_start)}.'
    if state == 'closed':
        return f'Pre-orders for "{product.name}" closed on {fmt_dt(product.preorder_end)}.'

    remaining = variant.preorder_remaining
    if remaining is None:
        return None
    label = f'"{product.name}" ({variant.variant_name})'
    if remaining <= 0:
        return f'{label} is fully booked.'
    if quantity + already_in_cart > remaining:
        return f'Only {remaining} pre-order slot{"s" if remaining != 1 else ""} left for {label}.'
    return None


def cart_block_reasons(items):
    """{cart_item_id: reason} for pre-order lines that can't be checked out right now.
    Lines of the same variation (different sizes) share its remaining slots."""
    totals = {}
    for it in items:
        totals[it.variant_id] = totals.get(it.variant_id, 0) + it.quantity
    out = {}
    for it in items:
        product = it.variant.product
        if product.pre_order:
            reason = preorder_block_reason(product, it.variant, totals[it.variant_id])
            if reason:
                out[it.id] = reason
    return out


def release_preorder_quantity(po, previous_status=None):
    """Give a pre-order's slots back after it was rejected / cancelled (never above the limit)."""
    if previous_status is not None and (previous_status or '').upper() in RELEASED_STATUSES:
        return False                      # already released
    if po.checkout_batch is None:
        return False                      # created before slot limits existed
    variant = po.product_variant
    if variant is None or variant.preorder_limit is None:
        return False
    type(variant).objects.filter(pk=variant.pk).update(
        stocks=Least(F('stocks') + po.quantity, F('preorder_limit'))
    )
    return True