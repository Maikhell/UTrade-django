import base64
import logging
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import OnlinePayment, Order, PreOrderRequest, User
from .utils import log_action, send_email

logger = logging.getLogger(__name__)
PAID, PENDING = OnlinePayment.STATUS_PAID, OnlinePayment.STATUS_PENDING
API = "https://api.paymongo.com/v1/checkout_sessions"


def _headers():
    key = base64.b64encode(f"{settings.PAYMONGO_SECRET_KEY}:".encode()).decode()
    return {"accept": "application/json", "content-type": "application/json",
            "authorization": f"Basic {key}"}


# ---------------- PayMongo ----------------
def create_checkout_session(request, payables, success_url, cancel_url):
    """payables = [{'name': str, 'amount': Decimal}]. Returns (checkout_url, session_id) or (None, None)."""
    try:
        payload = {"data": {"attributes": {
            "line_items": [{"currency": "PHP",
                            "amount": int((Decimal(p["amount"]) * 100).to_integral_value()),
                            "name": p["name"], "quantity": 1} for p in payables],
            "payment_method_types": ["gcash"],
            "success_url": success_url,
            "cancel_url": cancel_url,
        }}}
        r = requests.post(API, json=payload, headers=_headers(), timeout=20)
        data = r.json()["data"]
        return data["attributes"]["checkout_url"], data["id"]
    except Exception:
        logger.exception("PayMongo session failed")
        return None, None


def fetch_session_status(session_id):
    """Returns (is_paid, reference). Only trusts PayMongo, never the browser."""
    try:
        r = requests.get(f"{API}/{session_id}", headers=_headers(), timeout=20)
        attrs = r.json()["data"]["attributes"]
        for p in attrs.get("payments") or []:
            if p["attributes"].get("status") == "paid":
                return True, p["id"]
    except Exception:
        logger.exception("PayMongo status check failed for %s", session_id)
    return False, ""


# ---------------- Records ----------------
def _fmt_time(t):
    return t.strftime("%I:%M %p").lstrip("0") if t else ""


def ensure_payment(obj, kind, session_id=""):
    """Get or create the single payment record of an order / pre-order."""
    if kind == "order":
        buyer, seller, amount = obj.user, obj.seller, obj.total_amount
        items = list(obj.items.select_related("product_variant__product"))
        names = [f"{i.product_variant.product.name} ({i.product_variant.variant_name}) x{i.quantity}"
                 for i in items if i.product_variant]
        product = items[0].product_variant.product if items and items[0].product_variant else None
        course, section = buyer.course or "", buyer.section or ""
        lookup = {"order": obj}
    else:
        buyer, seller, amount = obj.buyer, obj.seller, obj.get_total_price()
        product = obj.product_variant.product
        names = [f"{product.name} ({obj.product_variant.variant_name}) x{obj.quantity}"]
        course = obj.course_at_time or buyer.course or ""
        section = obj.section_at_time or buyer.section or ""
        lookup = {"preorder": obj}

    payment, _ = OnlinePayment.objects.get_or_create(defaults=dict(
        buyer=buyer, seller=seller, amount=amount,
        buyer_name=buyer.get_full_name() or buyer.username or "",
        buyer_course=course, buyer_section=section,
        product_name="; ".join(names),
        pickup_location=(getattr(product, "meetup_location_text", "") or "") if product else "",
        pickup_days=(getattr(product, "available_days", "") or "") if product else "",
        pickup_time=(f"{_fmt_time(product.preferred_meetup_time_from)} - "
                     f"{_fmt_time(product.preferred_meetup_time_to)}"
                     if product and product.preferred_meetup_time_from else ""),
    ), **lookup)

    if session_id and payment.status != PAID and payment.checkout_session_id != session_id:
        payment.checkout_session_id = session_id
        payment.save(update_fields=["checkout_session_id"])
    return payment


@transaction.atomic
def mark_paid(payment_id, reference=""):
    """Idempotent: the single place where a payment becomes PAID."""
    p = OnlinePayment.objects.select_for_update(of=("self",)).get(pk=payment_id)
    if p.status == PAID:
        return p, False
    now = timezone.now()
    p.status, p.paid_at, p.reference_no = PAID, now, (reference or p.checkout_session_id)[:100]
    p.save(update_fields=["status", "paid_at", "reference_no"])

    if p.order_id:
        Order.objects.filter(pk=p.order_id, status="Pending").update(status="Paid", updated_at=now)
    if p.preorder_id:
        PreOrderRequest.objects.filter(pk=p.preorder_id).update(is_paid=True, updated_at=now)

    transaction.on_commit(lambda: notify_cbrgu_heads(p.pk))
    return p, True


def confirm_online_payments(payments):
    """Ask PayMongo about each pending payment (one call per session) and mark the paid ones."""
    cache = {}
    for p in payments:
        sid = p.checkout_session_id
        if p.status == PAID or not sid:
            continue
        if sid not in cache:
            cache[sid] = fetch_session_status(sid)
        paid, ref = cache[sid]
        if paid:
            mark_paid(p.pk, ref)


def confirm_pending(user, **filters):
    qs = OnlinePayment.objects.filter(buyer=user, status=PENDING).exclude(checkout_session_id="")
    if filters:
        qs = qs.filter(**filters)
    confirm_online_payments(list(qs))


# ---------------- Notifications ----------------
def notify_cbrgu_heads(payment_id):
    """Runs once per payment (the timestamp update is the lock)."""
    if not OnlinePayment.objects.filter(pk=payment_id, head_notified_at__isnull=True)\
            .update(head_notified_at=timezone.now()):
        return
    p = OnlinePayment.objects.select_related("buyer", "seller").get(pk=payment_id)
    try:
        log_action(user=p.buyer, action="Online Payment Received", item_type="Payment",
                   item_name=p.product_name[:100] or f"Payment #{p.pk}",
                   details=f"GCash PHP {p.amount} from {p.buyer_name} to seller "
                           f"{p.seller.get_full_name() or p.seller.username}. Ref {p.reference_no}")
    except Exception:
        logger.exception("log_action failed for payment %s", p.pk)

    subject = f"UTrade – GCash payment received (PHP {p.amount})"
    body = (f"A buyer completed an online payment.\n\nBuyer: {p.buyer_name} "
            f"({p.buyer_course} {p.buyer_section})\nProduct: {p.product_name}\n"
            f"Amount: PHP {p.amount}\nReference: {p.reference_no}\n\n"
            f"Open Payments in the CBRGU panel to notify the seller.")
    for head in User.objects.filter(user_role="management", is_active=True).exclude(email=""):
        try:
            send_email(head.email, subject, body)
        except Exception:
            logger.exception("Head email failed for payment %s", p.pk)


def send_seller_payment_email(payment_id, sent_by):
    """Returns (ok, message, http_status). Sends at most once per payment."""
    try:
        with transaction.atomic():
            p = OnlinePayment.objects.select_for_update(of=("self",)).get(pk=payment_id)
            if p.status != PAID:
                return False, "This payment is not completed.", 400
            if p.seller_notified_at:
                when = timezone.localtime(p.seller_notified_at).strftime("%b %d, %Y %I:%M %p")
                return False, f"Seller was already notified on {when}.", 409
            seller = User.objects.get(pk=p.seller_id)
            if not (seller.email or "").strip():
                return False, "The seller has no email address on file.", 400

            pickup = "\n".join(filter(None, [
                f"  - Location: {p.pickup_location}" if p.pickup_location else "",
                f"  - Days: {p.pickup_days}" if p.pickup_days else "",
                f"  - Time: {p.pickup_time}" if p.pickup_time else "",
            ])) or "  - As agreed with the buyer on campus."
            body = (
                f"Hi {seller.get_full_name() or seller.username},\n\n"
                f"Good news! The item below has been PAID ONLINE via GCash.\n\n"
                f"Buyer: {p.buyer_name}\n"
                f"Course & Section: {p.buyer_course} {p.buyer_section}\n"
                f"Product: {p.product_name}\n"
                f"Amount paid: PHP {p.amount:,.2f}\n"
                f"Reference: {p.reference_no}\n\n"
                f"Pickup instructions:\n{pickup}\n"
                f"  - Please prepare the item and proceed with the pickup once it is ready.\n"
                f"  - Do not collect any additional payment; the buyer has already paid.\n"
                f"  - Meet in public campus areas and confirm the buyer's name before handing over.\n\n"
                f"Thank you,\nUTrade – CBRGU"
            )
            sent = send_email(
                seller.email.strip(),
                f"UTrade – Your item has been paid (PHP {p.amount:,.2f})",
                body,
            )
            if sent is False:      # in case your helper returns False instead of raising
                raise RuntimeError("send_email returned False")
            p.seller_notified_at, p.seller_notified_by = timezone.now(), sent_by
            p.save(update_fields=["seller_notified_at", "seller_notified_by"])
        log_action(user=sent_by, action="Seller Notified (Payment)", item_type="Payment",
                   item_name=f"Payment #{p.pk}", details=f"Emailed {seller.email}")
        return True, f"Email sent to {seller.get_full_name() or seller.username}.", 200
    except OnlinePayment.DoesNotExist:
        return False, "Payment not found.", 404
    except Exception:
        logger.exception("Seller email failed for payment %s", payment_id)
        return False, "Email could not be sent. Check the Gmail settings.", 502