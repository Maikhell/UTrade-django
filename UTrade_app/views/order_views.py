import traceback
import requests
import base64
import json
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from django.contrib import messages
from ..utils import accrue_platform_fee_for_order

from ..models import (
    CartItem,
    Order,
    OrderItem,
    Review,
    SellerReview,
    ProductVariant,
    ChatMessage,
    Conversation,
    PreOrderRequest,
)

# ---------------------------------------------------------------------------
# Order / pre-order progress, used by the "My Purchases" page
# ---------------------------------------------------------------------------
ORDER_STEPS = ['Placed', 'Accepted', 'In progress', 'Ready for pickup', 'Completed']
PREORDER_STEPS = ['Requested', 'Accepted', 'In progress', 'Ready for pickup', 'Completed']

# status -> (css key, label, step)
# step 0 = ended early (cancelled / rejected); len(steps) + 1 = every step done
ORDER_STATUS_META = {
    'Pending': ('pending', 'Pending', 1),
    'Paid': ('pending', 'Paid · awaiting seller', 1),
    'Accepted': ('accepted', 'Accepted', 2),
    'Processing': ('progress', 'Processing', 3),
    'Awaiting Payment': ('progress', 'Awaiting payment', 3),
    'Waiting for Stocks': ('progress', 'Waiting for stocks', 3),
    'Delivered': ('ready', 'Ready for pickup', 4),
    'Completed': ('completed', 'Completed', 6),
    'Cancelled': ('cancelled', 'Cancelled', 0),
    'Rejected': ('rejected', 'Rejected', 0),
}

PREORDER_STATUS_META = {
    'PENDING': ('pending', 'Pending', 1),
    'ACCEPTED': ('accepted', 'Accepted', 2),
    'APPROVED': ('accepted', 'Accepted', 2),
    'PROCESSING': ('progress', 'Processing', 3),
    'PREPARING': ('progress', 'Preparing', 3),
    'AWAITING_PAYMENT': ('progress', 'Awaiting payment', 3),
    'WAITING_STOCKS': ('progress', 'Waiting for stocks', 3),
    'READY': ('ready', 'Ready for pickup', 4),
    'COMPLETED': ('completed', 'Completed', 6),
    'REJECTED': ('rejected', 'Rejected', 0),
    'DECLINED': ('cancelled', 'Cancelled', 0),
    'CANCELLED': ('cancelled', 'Cancelled', 0),
}

PREORDER_IN_PROGRESS = {
    'PENDING', 'ACCEPTED', 'APPROVED', 'PROCESSING', 'PREPARING',
    'AWAITING_PAYMENT', 'WAITING_STOCKS',
}

# Order statuses that always belong to the "In Progress" tab
ORDER_IN_PROGRESS = ('Pending', 'Paid', 'Processing', 'Awaiting Payment', 'Waiting for Stocks')


def _decorate(obj, meta, kind, n_steps, status):
    """Attach display info (colour key, label, step) used by the templates."""
    key, label, step = meta.get(status, ('pending', obj.status, 1))
    obj.kind = kind
    obj.ui_class = key
    obj.ui_label = label
    obj.step = step
    obj.in_flight = 1 <= step <= n_steps
    return obj


def _is_management_order(order):
    """CBRGU orders follow the full workflow, so "Accepted" is still in progress."""
    return bool(order.seller_id and getattr(order.seller, 'user_role', '') == 'management')


# ---------------------------------------------------------------------------
# Ratings: product ratings (Review) + seller ratings (SellerReview)
# ---------------------------------------------------------------------------
def _parse_rating(raw):
    """'4' -> 4; anything that is not a whole number from 1 to 5 -> None."""
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if 1 <= value <= 5 else None


# ---- Quick-rating presets (the dropdown in the rate modals) ----------------------
# (key, stars, label). Picking one fills in the stars; the buyer can still tap the
# stars to change them and always gets a free-text box for their own feedback.
# Edit these lists to change the dropdown; the server only accepts keys listed here.
PRODUCT_QUICK_FEEDBACK = [
    ('p5_described', 5, 'Exactly as described'),
    ('p5_quality',   5, 'Great quality'),
    ('p5_value',     5, 'Worth the price'),
    ('p4_good',      4, 'Good, minor flaws'),
    ('p3_okay',      3, 'Okay, average'),
    ('p2_below',     2, 'Below expectations'),
    ('p1_poor',      1, 'Not as described'),
]
SELLER_QUICK_FEEDBACK = [
    ('s5_friendly',  5, 'Friendly and easy to deal with'),
    ('s5_ontime',    5, 'On time at the meetup'),
    ('s5_replies',   5, 'Fast replies'),
    ('s4_good',      4, 'Good overall'),
    ('s3_okay',      3, 'Okay, average'),
    ('s2_slow',      2, 'Late or slow to reply'),
    ('s1_poor',      1, 'Unreliable, poor experience'),
]
_PRODUCT_QUICK = {k: (stars, label) for k, stars, label in PRODUCT_QUICK_FEEDBACK}
_SELLER_QUICK = {k: (stars, label) for k, stars, label in SELLER_QUICK_FEEDBACK}


def _quick_options(presets):
    """Rows for the dropdown: key, stars and the text shown to the buyer."""
    return [
        {'key': k, 'stars': stars, 'display': f"{'★' * stars}{'☆' * (5 - stars)}  {label}"}
        for k, stars, label in presets
    ]


def _quick_label(key, table, rating):
    """
    Preset key -> its label, or '' when the key is unknown or does not match the
    final star rating (e.g. the buyer picked a preset and then changed the stars).
    """
    entry = table.get((key or '').strip())
    return entry[1] if entry and entry[0] == rating else ''


def _order_sellers(order):
    """Distinct sellers of the items in this order (falls back to order.seller)."""
    sellers = {}
    for item in order.items.all():
        variant = item.product_variant
        product = variant.product if variant else None
        seller = product.seller if product else None
        if seller:
            sellers[seller.id] = seller
    if not sellers and order.seller_id:
        sellers[order.seller_id] = order.seller
    return list(sellers.values())


def _attach_seller_ratings(order, buyer):
    """
    Adds to the order, for the templates:
      order.seller_rows     [{'seller', 'review', 'rating_field', 'quick_field', 'comment_field'}, ...]
      order.sellers_pending the rows the buyer has not rated yet
      order.product_review  the buyer's product rating for this order (or None)
      order.rate_pending    True while the buyer can still rate the products or a seller
    """
    order.seller_rows = []
    order.sellers_pending = []
    order.product_review = None
    order.rate_pending = False
    if order.status != 'Completed':
        return order

    order.product_review = next(
        (r for r in order.order_reviews.all() if r.user_id == buyer.id), None
    )
    mine = {r.seller_id: r for r in order.seller_reviews.all() if r.reviewer_id == buyer.id}
    for seller in _order_sellers(order):
        if seller.id == buyer.id:
            continue  # you cannot rate yourself
        order.seller_rows.append({
            'seller': seller,
            'review': mine.get(seller.id),
            'rating_field': f'seller_rating_{seller.id}',
            'quick_field': f'seller_quick_{seller.id}',
            'comment_field': f'seller_comment_{seller.id}',
        })
    order.sellers_pending = [row for row in order.seller_rows if row['review'] is None]
    order.rate_pending = (not order.is_rated) or bool(order.sellers_pending)
    return order


def _attach_preorder_ratings(po, buyer):
    """
    Same idea for a pre-order (one product, one seller). Adds:
      po.product_review / po.seller_review   the buyer's existing ratings (or None)
      po.can_rate_product / po.can_rate_seller
      po.rate_pending
    """
    po.product_review = None
    po.seller_review = None
    po.can_rate_product = False
    po.can_rate_seller = False
    po.rate_pending = False
    if (po.status or '').upper() != 'COMPLETED':
        return po

    po.product_review = next(
        (r for r in po.preorder_reviews.all() if r.user_id == buyer.id), None
    )
    po.seller_review = next(
        (r for r in po.seller_reviews.all()
         if r.reviewer_id == buyer.id and r.seller_id == po.seller_id), None
    )
    has_product = bool(po.product_variant_id and po.product_variant.product_id)
    po.can_rate_product = has_product and po.product_review is None
    po.can_rate_seller = bool(po.seller_id) and po.seller_id != buyer.id and po.seller_review is None
    po.rate_pending = po.can_rate_product or po.can_rate_seller
    return po


@login_required
@transaction.atomic
def place_order(request):
    if request.method != "POST":
        return redirect('cart_detail')

    payment_method = request.POST.get('payment_method')
    item_ids = request.POST.getlist('item_ids')

    if payment_method == "GCASH_ONLINE":
        payment_method = "GCASH"

    selected_items = CartItem.objects.filter(
        id__in=item_ids,
        cart__user=request.user,
    ).select_related('variant', 'variant__product')

    if not selected_items.exists():
        return redirect('cart_detail')

    try:
        with transaction.atomic():
            total_price = sum(item.get_cost() for item in selected_items)
            first_item = selected_items.first()
            product = first_item.variant.product
            order_seller = product.seller

            # Location from product listing
            location_text = (getattr(product, 'meetup_location_text', None) or '').strip()

            new_order = Order.objects.create(
                user=request.user,
                seller=order_seller,
                total_amount=total_price,
                payment_method=payment_method,
                pickup_location=location_text,
                meetup_location=location_text,
                buyer_note=request.POST.get('buyer_note') or '',
                status='Pending',
            )

            for item in selected_items:
                variant = item.variant
                if variant.stocks < item.quantity:
                    raise Exception(f"Not enough stock for {variant.product.name}")
                variant.stocks -= item.quantity
                variant.save(update_fields=['stocks'])

                OrderItem.objects.create(
                    order=new_order,
                    product_variant=variant,
                    price=variant.price,
                    quantity=item.quantity,
                )

        if payment_method == "GCASH":
            url = "https://api.paymongo.com/v1/checkout_sessions"
            secret_key = settings.PAYMONGO_SECRET_KEY
            encoded_key = base64.b64encode(f"{secret_key}:".encode()).decode()

            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": f"Basic {encoded_key}",
            }

            payload = {
                "data": {
                    "attributes": {
                        "line_items": [{
                            "currency": "PHP",
                            "amount": int(total_price * 100),
                            "name": f"UTrade Order #{new_order.id}",
                            "quantity": 1,
                        }],
                        "payment_method_types": ["gcash"],
                        "success_url": f"http://127.0.0.1:8000/order/success/{new_order.id}/",
                        "cancel_url": "http://127.0.0.1:8000/cart/",
                    }
                }
            }

            response = requests.post(url, json=payload, headers=headers)
            data = response.json()

            if "data" in data:
                checkout_url = data["data"]["attributes"]["checkout_url"]
                return redirect(checkout_url)

            print("PayMongo Error:", data)
            return redirect('cart_detail')

        return redirect('order_success', order_id=new_order.id)

    except Exception:
        print(traceback.format_exc())
        return redirect('cart_detail')


def submit_preorder_request(request, variant_id):
    if request.method == 'POST':
        try:
            variant = ProductVariant.objects.select_related('product', 'product__seller').get(id=variant_id)

            PreOrderRequest.objects.create(
                buyer=request.user,
                seller=variant.product.seller,
                product_variant=variant,
                status='PENDING',
                full_name_at_time=request.user.get_full_name(),
                student_no_at_time=getattr(request.user, 'student_no', '') or '',
                course_at_time=getattr(request.user, 'course', '') or '',
                section_at_time=getattr(request.user, 'section', '') or '',
            )

            return JsonResponse({'success': True, 'message': 'Request submitted'})

        except ProductVariant.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Variant not found'})

    return JsonResponse({'success': False, 'message': 'Invalid request'})


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.payment_method == "GCASH":
        order.status = "Paid"
        order.save(update_fields=['status'])

    CartItem.objects.filter(
        cart__user=request.user,
        variant__orderitem__order=order,
    ).delete()

    return render(request, 'UTrade_app/orders/success.html', {
        'order': order,
    })


@login_required
def order_history(request):
    orders = list(
        Order.objects.filter(user=request.user)
        .select_related('seller')
        .prefetch_related(
            'items__product_variant__product__seller',
            'items__product_variant__product__images',
            'order_reviews',
            'seller_reviews',
        )
        .order_by('-created_at')
    )
    for o in orders:
        _decorate(o, ORDER_STATUS_META, 'order', len(ORDER_STEPS), o.status)
        _attach_seller_ratings(o, request.user)

    preorders = list(
        PreOrderRequest.objects.filter(buyer=request.user)
        .select_related(
            'seller',
            'product_variant',
            'product_variant__product',
            'product_variant__product__seller',
        )
        .prefetch_related(
            'product_variant__product__images',
            'preorder_reviews',
            'seller_reviews',
        )
        .order_by('-created_at')
    )
    for po in preorders:
        _decorate(po, PREORDER_STATUS_META, 'preorder', len(PREORDER_STEPS), (po.status or '').upper())
        _attach_preorder_ratings(po, request.user)

    # ---- Orders by tab ----
    active_orders = [
        o for o in orders
        if o.status in ORDER_IN_PROGRESS
        or (o.status == 'Accepted' and _is_management_order(o))
    ]
    pickup_orders = [
        o for o in orders
        if o.status == 'Delivered'
        or (o.status == 'Accepted' and not _is_management_order(o))
    ]
    completed = [o for o in orders if o.status == 'Completed']
    ended = [o for o in orders if o.status in ('Cancelled', 'Rejected')]

    # "Needs rating" now also covers sellers that have not been rated yet
    needs_rating = [o for o in completed if o.rate_pending]
    already_rated = [o for o in completed if not o.rate_pending]
    history_orders = needs_rating + already_rated + ended

    # ---- Pre-orders by tab ----
    preorder_active = [po for po in preorders if (po.status or '').upper() in PREORDER_IN_PROGRESS]
    preorder_ready = [po for po in preorders if (po.status or '').upper() == 'READY']
    preorder_history = [
        po for po in preorders
        if (po.status or '').upper() not in PREORDER_IN_PROGRESS
        and (po.status or '').upper() != 'READY'
    ]

    def newest_first(items):
        return sorted(items, key=lambda x: x.created_at, reverse=True)

    # Mixed lists (orders + pre-orders), one per tab
    active_items = newest_first(active_orders + preorder_active)
    pickup_items = newest_first(pickup_orders + preorder_ready)
    history_items = sorted(
        history_orders + preorder_history,
        key=lambda x: (
            0 if getattr(x, 'rate_pending', False) else 1,
            -x.created_at.timestamp(),
        ),
    )

    context = {
        # kept for backward compatibility
        'orders': orders,
        'pending_orders': active_orders,
        'pending_count': len(active_orders),
        'pickup_orders': pickup_orders,
        'pickup_count': len(pickup_orders),
        'history_orders': history_orders,
        'completed_orders': completed,
        'completed_count': len(completed),
        'preorders': preorders,
        'preorder_pending_count': len(preorder_active),
        'preorder_ready_count': len(preorder_ready),
        # used by the redesigned page
        'active_items': active_items,
        'pickup_items': pickup_items,
        'history_items': history_items,
        'all_items': active_items + pickup_items + history_items,
        'active_count': len(active_items),
        'pickup_total': len(pickup_items),
        'history_total': len(history_items),
        'order_steps': ORDER_STEPS,
        'preorder_steps': PREORDER_STEPS,
        # quick-rating dropdowns
        'product_quick_options': _quick_options(PRODUCT_QUICK_FEEDBACK),
        'seller_quick_options': _quick_options(SELLER_QUICK_FEEDBACK),
    }
    return render(request, 'UTrade_app/orders/history.html', context)


@login_required
def accept_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, seller=request.user)

    if request.method == "POST":
        order.seller_note = request.POST.get('seller_note', '')

        # If location was empty at place time, allow seller to set it on accept
        loc = (request.POST.get('pickup_location') or '').strip()
        if loc:
            order.pickup_location = loc
            order.meetup_location = loc
        elif not order.pickup_location:
            # fallback: first product's meetup text
            first = order.items.select_related(
                'product_variant__product'
            ).first()
            if first and first.product_variant and first.product_variant.product:
                text = (first.product_variant.product.meetup_location_text or '').strip()
                order.pickup_location = text
                order.meetup_location = text

        if order.status in ['Pending', 'Paid']:
            order.status = 'Accepted'
            order.save(update_fields=[
                'status',
                'seller_note',
                'pickup_location',
                'meetup_location',
            ])
            messages.success(request, f"Order #{order.id} has been accepted!")
        else:
            messages.warning(request, "This order cannot be accepted.")

    return redirect('seller_inventory')


@login_required
def mark_order_delivered(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, seller=request.user)

        if order.status != 'Accepted':
            messages.error(request, "Only accepted orders can be marked as completed.")
            return redirect('seller_inventory')

        order.status = 'Completed'
        order.save(update_fields=['status', 'updated_at'])

        # Increment product sold counts
        for item in order.items.all():
            product = item.product_variant.product
            product.sold += item.quantity
            product.save(update_fields=['sold'])

        # Accrue platform fee & ledger record
        accrue_platform_fee_for_order(order)

        messages.success(request, f"Order #{order.id} has been marked as Completed.")

    return redirect('seller_inventory')


@login_required
def confirm_receipt(request, order_id):
    """
    Buyers are not allowed to mark an order as delivered/completed.
    Only the seller (or management) can do that, which also updates sold counts
    and the platform-fee ledger. The URL is kept so old links don't 404.
    """
    messages.error(
        request,
        "Orders are marked as completed by the seller. "
        "You'll be able to rate the order once it is completed.",
    )
    return redirect('order_history')


@login_required
@require_POST
def update_preorder_status(request, order_id):
    """Buyer action on a PreOrderRequest: a buyer may only cancel a pending pre-order."""
    try:
        data = json.loads(request.body)
        new_status = (data.get('status') or '').upper()
        reason = (data.get('reason') or '').strip()

        po = get_object_or_404(PreOrderRequest, id=order_id, buyer=request.user)

        if new_status != 'DECLINED':
            return JsonResponse(
                {'success': False, 'message': 'Buyers can only cancel a pending pre-order.'},
                status=403,
            )

        if (po.status or '').upper() != 'PENDING':
            return JsonResponse(
                {'success': False, 'message': 'Only pending pre-orders can be cancelled.'},
                status=400,
            )
        if not reason:
            return JsonResponse(
                {'success': False, 'message': 'Cancellation reason is required.'},
                status=400,
            )

        po.status = 'DECLINED'
        po.rejection_reason = 'Buyer request'
        po.rejection_note = reason
        po.save(update_fields=['status', 'rejection_reason', 'rejection_note', 'updated_at'])
        return JsonResponse({'success': True, 'message': 'Pre-order cancelled.'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@transaction.atomic
def cancel_order(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)

        if order.status != 'Pending':
            return JsonResponse(
                {'status': 'error', 'message': 'Order cannot be cancelled.'},
                status=400,
            )

        for item in order.items.all():
            variant = item.product_variant
            if variant:
                variant.stocks += item.quantity
                variant.save(update_fields=['stocks'])

        reason = request.POST.get('reason', 'No reason provided')
        order.status = 'Cancelled'
        order.cancellation_reason = reason
        order.save(update_fields=['status', 'cancellation_reason'])

        first_item = order.items.first()
        product = first_item.product_variant.product if first_item and first_item.product_variant else None

        if product:
            conversation, _ = Conversation.objects.get_or_create(
                product=product,
                buyer=request.user,
                seller=order.seller,
            )
            ChatMessage.objects.create(
                conversation=conversation,
                user=request.user,
                content=(
                    f"🚨 SYSTEM: Order #{order.id} has been cancelled by the buyer.\n"
                    f"Reason: {reason}"
                ),
                is_read=False,
            )

        return JsonResponse({'status': 'success', 'message': 'Order cancelled successfully.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request.'}, status=400)


@login_required
@transaction.atomic
def submit_review(request, order_id):
    """
    One form, two kinds of rating on a completed order:
      - the products   (fields: rating, quick, comment)
      - each seller    (fields: seller_rating_<id>, seller_quick_<id>, seller_comment_<id>)
    `quick` is the dropdown preset; `comment` is the buyer's own feedback.
    Every part is optional on its own, but at least one rating is required.
    """
    if request.method != 'POST':
        return redirect('order_history')

    order = get_object_or_404(
        Order.objects.prefetch_related(
            'items__product_variant__product__seller', 'order_reviews', 'seller_reviews'
        ),
        id=order_id,
        user=request.user,
    )

    if order.status != 'Completed':
        messages.error(request, "You can only rate completed orders.")
        return redirect('order_history')

    saved = 0

    # ---- Product rating (only while the order is not rated yet) ----
    product_raw = (request.POST.get('rating') or '').strip()
    if product_raw and not order.is_rated:
        rating_value = _parse_rating(product_raw)
        if rating_value is None:
            messages.error(request, "Product rating must be from 1 to 5 stars.")
            return redirect('order_history')
        comment = (request.POST.get('comment') or '').strip()[:1000]
        quick = _quick_label(request.POST.get('quick'), _PRODUCT_QUICK, rating_value)
        for item in order.items.all():
            Review.objects.update_or_create(
                order=order,
                product=item.product_variant.product,
                user=request.user,
                defaults={'rating': rating_value, 'comment': comment, 'quick_feedback': quick},
            )
        saved += 1

    # ---- Seller ratings ----
    # Only sellers that really sold something in this order can be rated.
    for seller in _order_sellers(order):
        if seller.id == request.user.id:
            continue
        raw = (request.POST.get(f'seller_rating_{seller.id}') or '').strip()
        if not raw:
            continue
        seller_rating = _parse_rating(raw)
        if seller_rating is None:
            messages.error(request, "Seller rating must be from 1 to 5 stars.")
            return redirect('order_history')
        SellerReview.objects.update_or_create(
            order=order,
            seller=seller,
            reviewer=request.user,
            defaults={
                'rating': seller_rating,
                'quick_feedback': _quick_label(
                    request.POST.get(f'seller_quick_{seller.id}'), _SELLER_QUICK, seller_rating
                ),
                'comment': (request.POST.get(f'seller_comment_{seller.id}') or '').strip()[:1000],
            },
        )
        saved += 1

    if not saved:
        messages.warning(request, "Please choose a star rating first.")
    else:
        messages.success(request, "Thank you for your review!")
    return redirect('order_history')


@login_required
@transaction.atomic
def submit_preorder_review(request, preorder_id):
    """
    Rate a COMPLETED pre-order: the product (rating, quick, comment) and/or the
    seller (seller_rating, seller_quick, seller_comment). At least one is required.
    """
    if request.method != 'POST':
        return redirect('order_history')

    po = get_object_or_404(
        PreOrderRequest.objects
        .select_related('seller', 'product_variant__product')
        .prefetch_related('preorder_reviews', 'seller_reviews'),
        id=preorder_id,
        buyer=request.user,
    )

    if (po.status or '').upper() != 'COMPLETED':
        messages.error(request, "You can only rate completed pre-orders.")
        return redirect('order_history')

    saved = 0

    # ---- Product ----
    product = po.product_variant.product if po.product_variant_id else None
    product_done = any(r.user_id == request.user.id for r in po.preorder_reviews.all())
    product_raw = (request.POST.get('rating') or '').strip()
    if product_raw and product and not product_done:
        rating_value = _parse_rating(product_raw)
        if rating_value is None:
            messages.error(request, "Product rating must be from 1 to 5 stars.")
            return redirect('order_history')
        Review.objects.update_or_create(
            preorder=po,
            product=product,
            user=request.user,
            defaults={
                'rating': rating_value,
                'quick_feedback': _quick_label(request.POST.get('quick'), _PRODUCT_QUICK, rating_value),
                'comment': (request.POST.get('comment') or '').strip()[:1000],
            },
        )
        saved += 1

    # ---- Seller ----
    seller = po.seller
    seller_raw = (request.POST.get('seller_rating') or '').strip()
    if seller_raw and seller and seller.id != request.user.id:
        seller_rating = _parse_rating(seller_raw)
        if seller_rating is None:
            messages.error(request, "Seller rating must be from 1 to 5 stars.")
            return redirect('order_history')
        SellerReview.objects.update_or_create(
            preorder=po,
            seller=seller,
            reviewer=request.user,
            defaults={
                'rating': seller_rating,
                'quick_feedback': _quick_label(request.POST.get('seller_quick'), _SELLER_QUICK, seller_rating),
                'comment': (request.POST.get('seller_comment') or '').strip()[:1000],
            },
        )
        saved += 1

    if not saved:
        messages.warning(request, "Please choose a star rating first.")
    else:
        messages.success(request, "Thank you for your review!")
    return redirect('order_history')


@login_required
def generate_receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    context = {
        'order': order,
        'items': order.items.select_related('product_variant', 'product_variant__product'),
        'buyer': request.user,
        'seller': order.seller,
        'is_preorder': False,
    }

    html_string = render_to_string('UTrade_app/reports/receipt_pdf.html', context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Receipt_Order_{order.id}.pdf"'
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    return response


@login_required
def generate_preorder_receipt(request, preorder_id):
    preorder = get_object_or_404(
        PreOrderRequest,
        id=preorder_id,
        buyer=request.user,
        status='COMPLETED',
    )

    context = {
        'order': preorder,
        'buyer': preorder.buyer,
        'is_preorder': True,
        'date': preorder.updated_at,
    }

    html_string = render_to_string('UTrade_app/reports/receipt_pdf.html', context)
    result = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="PreOrder_Receipt_{preorder.id}.pdf"'
    response.write(result)
    return response