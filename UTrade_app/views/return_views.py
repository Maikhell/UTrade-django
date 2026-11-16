"""
Product returns for Orders AND Pre-orders (one code path, `kind` = 'order' | 'preorder').

Flow
----
Completed --(buyer, within 48h)--> Return Requested
Return Requested --(seller accepts: location + date + time range)--> Waiting for Product
Return Requested --(seller rejects: reason)--> Return Rejected
Waiting for Product --(seller: product received)--> Refund      (resolution = Refund)
                                              +--> Returned     (resolution = Replacement / Exchange)
Refund --(seller: refund issued)--> Returned

Every transition is validated here on the server; the templates only hide buttons.
"""
import json
import logging
import mimetypes
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.http import require_POST

from ..models import (
    ChatMessage,
    Conversation,
    MeetupLocation,
    Order,
    OrganizationPlatformLedger,
    PlatformFeeLine,
    PreOrderRequest,
    ProductVariant,
    ReturnImage,
)
from ..utils import is_allowed_email, log_action, send_email

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
MIN_RETURN_IMAGES = 1
MAX_RETURN_IMAGES = 4
MAX_IMAGE_BYTES = 3 * 1024 * 1024          # per image (also keeps the seller email small)
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}

# status values per kind. PreOrderRequest.status is max_length=20, all of these fit.
RETURN_STATUS = {
    'order': {
        'completed': 'Completed',
        'requested': 'Return Requested',
        'waiting': 'Waiting for Product',
        'refund': 'Refund',
        'returned': 'Returned',
        'rejected': 'Return Rejected',
    },
    'preorder': {
        'completed': 'COMPLETED',
        'requested': 'RETURN_REQUESTED',
        'waiting': 'WAITING_PRODUCT',
        'refund': 'REFUND',
        'returned': 'RETURNED',
        'rejected': 'RETURN_REJECTED',
    },
}
STAGES = ('requested', 'waiting', 'refund', 'returned', 'rejected')
STAGE_LABEL = {
    'requested': 'Return requested',
    'waiting': 'Waiting for product',
    'refund': 'Refund',
    'returned': 'Returned',
    'rejected': 'Return rejected',
}
MODELS = {'order': Order, 'preorder': PreOrderRequest}


class ReturnError(Exception):
    """A validation / permission problem that should be shown to the user."""


def _model(kind):
    if kind not in MODELS:
        raise Http404("Unknown kind")
    return MODELS[kind]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _items_of(obj, kind):
    """[(variant, qty)] for an order (all items) or a pre-order (one item)."""
    if kind == 'order':
        return [(i.product_variant, i.quantity) for i in obj.items.all() if i.product_variant]
    return [(obj.product_variant, obj.quantity)] if obj.product_variant_id else []


def _product_names(obj, kind):
    names = []
    for variant, qty in _items_of(obj, kind):
        names.append(f"{variant.product.name} ({variant.variant_name}) x{qty}")
    return ", ".join(names) or "your item"


def _ref(obj, kind):
    if kind == 'order':
        return f"Order {obj.order_number or '#' + str(obj.id)}"
    return f"Pre-order #{obj.id}"


def _name(user):
    return (user.get_full_name() or user.username) if user else "—"


def _seller_can_manage(user, obj):
    if obj.seller_id == user.id:
        return True
    org_id = getattr(user, 'org_link_id', None)
    return bool(org_id and obj.seller_id and getattr(obj.seller, 'org_link_id', None) == org_id)


def exchange_options(obj, kind):
    """Other variations of the ordered product(s) the buyer can exchange for."""
    ordered_ids, products = set(), {}
    for variant, _qty in _items_of(obj, kind):
        ordered_ids.add(variant.id)
        products[variant.product_id] = variant.product
    options = []
    for product in products.values():
        for v in product.variants.all():
            if v.id in ordered_ids:
                continue
            if kind == 'order' and v.stocks <= 0:
                continue
            label = f"{product.name} – {v.variant_name}"
            if kind == 'order':
                label += f" ({v.stocks} in stock)"
            options.append({'id': v.id, 'label': label})
    return options


def attach_return_info(obj, kind):
    """
    Display / eligibility info for the templates. Adds:
      return_stage ('' | requested | waiting | refund | returned | rejected), return_stage_label,
      can_return, return_expired, return_deadline_iso, exchange_options_json, return_image_list
    """
    st = RETURN_STATUS[kind]
    stage = next((s for s in STAGES if (obj.status or '') == st[s]), '')
    obj.return_stage = stage
    obj.return_stage_label = STAGE_LABEL.get(stage, '')
    obj.is_return_state = bool(stage)

    completed = (obj.status or '') == st['completed']
    obj.can_return = completed and obj.can_request_return
    obj.return_expired = completed and not obj.return_requested_at and not obj.can_return
    deadline = obj.return_deadline
    obj.return_deadline_iso = deadline.isoformat() if deadline else ''
    obj.exchange_options_json = json.dumps(exchange_options(obj, kind)) if obj.can_return else '[]'
    obj.return_image_list = list(obj.return_images.all()) if (stage or obj.return_requested_at) else []
    return obj


def org_return_context(base_qs, kind):
    """Context for the seller 'Returns' and 'Refund' tabs (orders page + pre-orders page)."""
    st = RETURN_STATUS[kind]
    returns_qs = base_qs.filter(
        status__in=[st['requested'], st['waiting'], st['rejected'], st['returned']]
    ).prefetch_related('return_images').order_by('-return_requested_at')
    refund_qs = base_qs.filter(status=st['refund']).prefetch_related(
        'return_images'
    ).order_by('-return_requested_at')

    return_items = list(returns_qs[:100])
    refund_items = list(refund_qs[:100])
    for obj in return_items + refund_items:
        attach_return_info(obj, kind)
    return {
        'return_kind': kind,
        'return_items': return_items,
        'refund_items': refund_items,
        'return_count': returns_qs.count(),
        'refund_count': refund_qs.count(),
        'return_new_count': base_qs.filter(status=st['requested']).count(),
        'return_locations': MeetupLocation.objects.all().order_by('name'),
    }


# ---------------------------------------------------------------------------
# Chat + email
# ---------------------------------------------------------------------------
def _chat(actor, obj, kind, text):
    try:
        variants = _items_of(obj, kind)
        product = variants[0][0].product if variants else None
        if not product or not obj.seller_id:
            return
        conversation, _ = Conversation.objects.get_or_create(
            product=product, buyer=obj.return_buyer, seller=obj.seller
        )
        ChatMessage.objects.create(conversation=conversation, user=actor, content=text, is_read=False)
    except Exception:
        logger.exception("Return chat notification failed for %s %s", kind, obj.pk)


def _send(subject, body, to, attachments=None):
    if not to:
        return
    try:
        msg = EmailMessage(subject, body, getattr(settings, 'DEFAULT_FROM_EMAIL', None), [to])
        for name, data, mime in attachments or []:
            msg.attach(name, data, mime)
        msg.send(fail_silently=True)
    except Exception:
        logger.exception("Return email to %s failed", to)


def _buyer_email(user):
    """Same rule the order/pre-order boards use for buyer emails (utils.is_allowed_email)."""
    email = (getattr(user, 'email', '') or '').strip().lower()
    return email if email and is_allowed_email(email) else ''


def _seller_email(obj):
    return (getattr(obj.seller, 'email', '') or '').strip()


def _fmt_schedule(obj):
    d = obj.return_date.strftime('%A, %B %d, %Y') if obj.return_date else '—'
    tf = obj.return_time_from.strftime('%I:%M %p').lstrip('0') if obj.return_time_from else ''
    tt = obj.return_time_to.strftime('%I:%M %p').lstrip('0') if obj.return_time_to else ''
    return d, f"{tf} – {tt}"


def email_seller_new_return(kind, pk):
    obj = _model(kind).objects.select_related('seller').get(pk=pk)
    to = _seller_email(obj)
    if not to:
        return
    extra = ""
    if obj.exchange_variant_id:
        extra = f"\nExchange for: {obj.exchange_variant}"
    body = (
        f"Hi {_name(obj.seller)},\n\n"
        f"{_name(obj.return_buyer)} requested a return for {_ref(obj, kind)}.\n\n"
        f"Product(s): {_product_names(obj, kind)}\n"
        f"Requested resolution: {obj.return_resolution}{extra}\n"
        f"Reason: {obj.get_return_reason_display()}\n"
        f"Details: {obj.return_note or '—'}\n\n"
        f"The buyer's photos are attached ({obj.return_images.count()}).\n"
        f"Open your Returns tab in UTrade to accept or reject this request.\n\n"
        f"Thank you for using UTrade."
    )
    attachments = []
    for img in obj.return_images.all():
        try:
            img.image.open('rb')
            data = img.image.read()
            img.image.close()
            name = os.path.basename(img.image.name)
            attachments.append((name, data, mimetypes.guess_type(name)[0] or 'image/jpeg'))
        except Exception:
            logger.exception("Could not attach return image %s", img.pk)
    _send(f"UTrade – Return request for {_ref(obj, kind)}", body, to, attachments)


def email_buyer_return_accepted(kind, pk):
    obj = _model(kind).objects.select_related('seller').get(pk=pk)
    to = _buyer_email(obj.return_buyer)
    d, t = _fmt_schedule(obj)
    body = (
        f"Hi {_name(obj.return_buyer)},\n\n"
        f"Your return request for {_ref(obj, kind)} has been ACCEPTED by {_name(obj.seller)}.\n\n"
        f"Requested resolution: {obj.return_resolution}\n"
        f"Return location: {obj.return_pickup_location}\n"
        f"Date: {d}\n"
        f"Time: {t}\n\n"
        f"Please bring the product (with its packaging and accessories if possible) to the location "
        f"within that time range. Your return continues once the seller receives it.\n\n"
        f"Thank you for using UTrade."
    )
    if to:
        send_email(to, f"UTrade – Return accepted for {_ref(obj, kind)}", body)


def email_buyer_return_rejected(kind, pk):
    obj = _model(kind).objects.select_related('seller').get(pk=pk)
    to = _buyer_email(obj.return_buyer)
    body = (
        f"Hi {_name(obj.return_buyer)},\n\n"
        f"Unfortunately your return request for {_ref(obj, kind)} was REJECTED by {_name(obj.seller)}.\n\n"
        f"Reason: {obj.return_response_note or 'Not specified'}\n\n"
        f"You can message the seller in UTrade if you need clarification.\n\n"
        f"Thank you for using UTrade."
    )
    if to:
        send_email(to, f"UTrade – Return rejected for {_ref(obj, kind)}", body)


# ---------------------------------------------------------------------------
# Buyer: request a return
# ---------------------------------------------------------------------------
def _validate_images(files):
    if len(files) < MIN_RETURN_IMAGES:
        raise ReturnError("Please upload at least one photo of the product.")
    if len(files) > MAX_RETURN_IMAGES:
        raise ReturnError(f"You can upload up to {MAX_RETURN_IMAGES} photos.")
    from PIL import Image
    for f in files:
        if f.content_type not in ALLOWED_IMAGE_TYPES:
            raise ReturnError("Photos must be JPG, PNG or WEBP.")
        if f.size > MAX_IMAGE_BYTES:
            raise ReturnError(f"Each photo must be {MAX_IMAGE_BYTES // (1024 * 1024)} MB or smaller.")
        try:
            Image.open(f).verify()
        except Exception:
            raise ReturnError(f"'{f.name}' is not a valid image.")
        f.seek(0)


@login_required
@require_POST
def request_return(request, kind, pk):
    Model = _model(kind)
    st = RETURN_STATUS[kind]
    owner_field = 'user' if kind == 'order' else 'buyer'
    try:
        with transaction.atomic():
            obj = get_object_or_404(Model.objects.select_for_update(), pk=pk, **{owner_field: request.user})

            if (obj.status or '') != st['completed']:
                raise ReturnError("Only completed purchases can be returned.")
            if obj.return_requested_at:
                raise ReturnError("A return was already requested for this purchase.")
            if not obj.can_request_return:
                raise ReturnError("The 48-hour return window for this purchase has closed.")

            resolution = (request.POST.get('resolution') or '').strip()
            reason = (request.POST.get('reason') or '').strip()
            details = (request.POST.get('details') or '').strip()[:1000]
            if resolution not in dict(Model.RETURN_RESOLUTION_CHOICES):
                raise ReturnError("Please choose what you want: refund, replacement or exchange.")
            if reason not in dict(Model.RETURN_REASON_CHOICES):
                raise ReturnError("Please select a reason.")
            if len(details) < 5:
                raise ReturnError("Please describe the problem.")

            exchange_variant = None
            if resolution == Model.RESOLUTION_EXCHANGE:
                allowed = {o['id'] for o in exchange_options(obj, kind)}
                try:
                    vid = int(request.POST.get('exchange_variant') or 0)
                except ValueError:
                    vid = 0
                if vid not in allowed:
                    raise ReturnError("Please choose the color, size or variation you want instead.")
                exchange_variant = ProductVariant.objects.get(pk=vid)

            files = request.FILES.getlist('images')
            _validate_images(files)

            obj.status = st['requested']
            obj.return_resolution = resolution
            obj.return_reason = reason
            obj.return_note = details
            obj.exchange_variant = exchange_variant
            obj.return_requested_at = timezone.now()
            obj.save(update_fields=[
                'status', 'return_resolution', 'return_reason', 'return_note',
                'exchange_variant', 'return_requested_at', 'updated_at',
            ])
            for f in files:
                ReturnImage.objects.create(
                    order=obj if kind == 'order' else None,
                    preorder=obj if kind == 'preorder' else None,
                    image=f,
                )
            transaction.on_commit(lambda: email_seller_new_return(kind, obj.pk))

        _chat(request.user, obj, kind,
              f"🚨 SYSTEM: Return requested for {_ref(obj, kind)}.\n"
              f"Resolution: {obj.return_resolution}\nReason: {obj.get_return_reason_display()}")
        return JsonResponse({'success': True, 'status': 'success',
                             'message': 'Return request sent to the seller.'})
    except ReturnError as exc:
        return JsonResponse({'success': False, 'status': 'error', 'message': str(exc)}, status=400)


# ---------------------------------------------------------------------------
# Seller: accept / reject / received / refunded
# ---------------------------------------------------------------------------
def _accept(request, obj, kind, st):
    if obj.status != st['requested']:
        raise ReturnError("This purchase has no pending return request.")
    location = (request.POST.get('location') or '').strip()
    day = parse_date(request.POST.get('date') or '')
    t_from = parse_time(request.POST.get('time_from') or '')
    t_to = parse_time(request.POST.get('time_to') or '')

    if not MeetupLocation.objects.filter(name=location).exists():
        raise ReturnError("Please choose a return location from the approved pickup locations.")
    if not (day and t_from and t_to):
        raise ReturnError("Please set the return date and time range.")
    if day < timezone.localdate():
        raise ReturnError("The return date cannot be in the past.")
    if t_from >= t_to:
        raise ReturnError("The end time must be after the start time.")
    if day == timezone.localdate() and t_to <= timezone.localtime().time():
        raise ReturnError("That time range has already passed today.")

    obj.status = st['waiting']
    obj.return_pickup_location = location
    obj.return_date = day
    obj.return_time_from = t_from
    obj.return_time_to = t_to
    obj.return_accepted_at = timezone.now()
    obj.save(update_fields=[
        'status', 'return_pickup_location', 'return_date', 'return_time_from',
        'return_time_to', 'return_accepted_at', 'updated_at',
    ])
    transaction.on_commit(lambda: email_buyer_return_accepted(kind, obj.pk))
    d, t = _fmt_schedule(obj)
    _chat(request.user, obj, kind,
          f"✅ SYSTEM: Return accepted for {_ref(obj, kind)}.\nBring the product to {location} on {d}, {t}.")
    return "Return accepted. The buyer was notified."


def _reject(request, obj, kind, st):
    if obj.status != st['requested']:
        raise ReturnError("This purchase has no pending return request.")
    reason = (request.POST.get('reason') or '').strip()[:500]
    if not reason:
        raise ReturnError("Please give a reason for rejecting the return.")
    obj.status = st['rejected']
    obj.return_response_note = reason
    obj.save(update_fields=['status', 'return_response_note', 'updated_at'])
    transaction.on_commit(lambda: email_buyer_return_rejected(kind, obj.pk))
    _chat(request.user, obj, kind, f"🚨 SYSTEM: Return rejected for {_ref(obj, kind)}.\nReason: {reason}")
    return "Return rejected. The buyer was notified."


def _apply_inventory(order, resolution):
    """Orders only. Pre-orders are made to order, so they don't touch stock."""
    items = list(order.items.select_related('product_variant__product'))
    if resolution == Order.RESOLUTION_REFUND:
        for it in items:
            if not it.product_variant_id:
                continue
            variant = ProductVariant.objects.select_for_update().get(pk=it.product_variant_id)
            variant.stocks += it.quantity
            variant.save(update_fields=['stocks'])
            product = variant.product
            product.sold = max(0, product.sold - it.quantity)
            product.save(update_fields=['sold'])
    elif resolution == Order.RESOLUTION_REPLACEMENT:
        # the buyer gets a new unit; the returned unit is not put back on sale
        for it in items:
            if not it.product_variant_id:
                continue
            variant = ProductVariant.objects.select_for_update().get(pk=it.product_variant_id)
            if variant.stocks < it.quantity:
                raise ReturnError(f"Not enough stock to replace {variant.product.name}.")
            variant.stocks -= it.quantity
            variant.save(update_fields=['stocks'])
    elif resolution == Order.RESOLUTION_EXCHANGE and order.exchange_variant_id:
        target = ProductVariant.objects.select_for_update().get(pk=order.exchange_variant_id)
        for it in items:
            if it.product_variant_id and it.product_variant.product_id == target.product_id:
                if target.stocks < it.quantity:
                    raise ReturnError(f"Not enough stock of '{target.variant_name}' for the exchange.")
                original = ProductVariant.objects.select_for_update().get(pk=it.product_variant_id)
                original.stocks += it.quantity          # returned item goes back on sale
                original.save(update_fields=['stocks'])
                target.stocks -= it.quantity            # exchange item leaves stock
                target.save(update_fields=['stocks'])
                break


def _reverse_platform_fee(order):
    """Undo the 3% platform fee of a refunded order, unless that cycle is already remitted."""
    line = PlatformFeeLine.objects.select_for_update().select_related('ledger').filter(order=order).first()
    if not line:
        return
    ledger = line.ledger
    if ledger.status == OrganizationPlatformLedger.STATUS_PAID:
        logger.warning("Order %s refunded after its fee cycle was remitted; fee not reversed.", order.pk)
        return
    ledger.accumulated_fee = max(ledger.accumulated_fee - line.fee_amount, 0)
    ledger.accumulated_sales = max(ledger.accumulated_sales - line.order_amount, 0)
    ledger.save(update_fields=['accumulated_fee', 'accumulated_sales', 'updated_at'])
    line.delete()


def _received(request, obj, kind, st):
    if obj.status != st['waiting']:
        raise ReturnError("This return is not waiting for the product.")
    now = timezone.now()
    obj.product_received_at = now
    if kind == 'order':
        _apply_inventory(obj, obj.return_resolution)
    if obj.return_resolution == obj.RESOLUTION_REFUND:
        obj.status = st['refund']
        msg = "Product received. Issue the refund, then mark it as refunded."
    else:
        obj.status = st['returned']
        obj.returned_at = now
        msg = f"Product received. {obj.return_resolution} completed."
    obj.save(update_fields=['status', 'product_received_at', 'returned_at', 'updated_at'])
    _chat(request.user, obj, kind, f"📦 SYSTEM: Product received for {_ref(obj, kind)}.")
    return msg


def _refunded(request, obj, kind, st):
    if obj.status != st['refund']:
        raise ReturnError("This purchase is not waiting for a refund.")
    now = timezone.now()
    obj.status = st['returned']
    obj.refunded_at = now
    obj.returned_at = now
    obj.save(update_fields=['status', 'refunded_at', 'returned_at', 'updated_at'])
    if kind == 'order':
        _reverse_platform_fee(obj)
    _chat(request.user, obj, kind, f"💸 SYSTEM: Refund issued for {_ref(obj, kind)}.")
    return "Refund recorded. The purchase is now Returned."


ACTIONS = {'accept': _accept, 'reject': _reject, 'received': _received, 'refunded': _refunded}


@login_required
@require_POST
def return_action(request, kind, pk, action):
    if action not in ACTIONS:
        raise Http404("Unknown action")
    Model = _model(kind)
    st = RETURN_STATUS[kind]
    try:
        with transaction.atomic():
            obj = get_object_or_404(Model.objects.select_for_update(), pk=pk)
            if not _seller_can_manage(request.user, obj):
                return JsonResponse({'success': False, 'message': 'Not allowed.'}, status=403)
            message = ACTIONS[action](request, obj, kind, st)
            log_action(
                user=request.user,
                action=f"Return {action.title()}",
                item_type="Order" if kind == 'order' else "PreOrder",
                item_name=_ref(obj, kind),
                details=f"Status → {obj.status}",
            )
        return JsonResponse({'success': True, 'message': message})
    except ReturnError as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)