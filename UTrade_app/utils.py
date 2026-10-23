from .models import SystemLog, Product, StagedProduct, OrganizationPlatformLedger, PlatformFeeLine
import random
import re
import logging
from datetime import timedelta

import resend
from django.conf import settings
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction

logger = logging.getLogger(__name__)

PLATFORM_FEE_RATE = Decimal('0.03')


def log_action(user, action, item_type, item_name, details=""):
    SystemLog.objects.create(
        user=user,
        action=action,
        item_type=item_type,
        item_name=item_name,
        details=details,
    )


def send_email(to, subject, text, html=None):
    """
    Send an email through Resend. Reusable for any email feature
    (OTP, order notifications, etc.).
    Raises on missing config or API failure so the caller can show a message.
    """
    api_key = getattr(settings, 'RESEND_API_KEY', None)
    if not api_key:
        raise RuntimeError('RESEND_API_KEY is not configured.')

    recipients = [to] if isinstance(to, str) else list(to)
    resend.api_key = api_key

    params = {
        'from': settings.DEFAULT_FROM_EMAIL,
        'to': recipients,
        'subject': subject,
        'text': text,
    }
    if html:
        params['html'] = html

    try:
        response = resend.Emails.send(params)
        logger.info('Email sent to %s (id=%s)', recipients, response.get('id'))
        return response
    except Exception:
        logger.exception('Email FAILED to %s subject=%r', recipients, subject)
        raise


def send_otp_email(user):
    """
    Generate a 6-digit OTP, store expiry on the user, email it to user.email via Resend.
    Raises on missing email or send failure so the caller can show a message.
    """
    recipient = (getattr(user, 'email', None) or '').strip()
    if not recipient:
        raise ValueError(f'User id={getattr(user, "id", None)} has no email for OTP.')

    otp = f'{random.randint(100000, 999999)}'
    user.otp_code = otp
    user.otp_expiry = timezone.now() + timedelta(minutes=10)
    user.save(update_fields=['otp_code', 'otp_expiry'])

    subject = 'Verify your UTrade Account'
    message = (
        f'Hi {user.first_name or user.username or "there"},\n\n'
        f'Your UTrade verification code is: {otp}\n\n'
        f'This code expires in 10 minutes.\n\n'
        f'If you did not register for UTrade, you can ignore this email.\n\n'
        f'— UTrade CVSU'
    )

    return send_email(recipient, subject, message)


def generate_next_product_code(model_cls=None):
    """
    Format: UTR-YYYY-####  (zero-padded, auto-increment per year)
    """
    year = timezone.now().year
    prefix = f'UTR-{year}-'

    def max_seq(qs):
        codes = qs.filter(product_code__startswith=prefix).values_list(
            'product_code', flat=True
        )
        best = 0
        for code in codes:
            m = re.search(r'(\d+)$', code or '')
            if m:
                best = max(best, int(m.group(1)))
        return best

    last = max(max_seq(Product.objects.all()), max_seq(StagedProduct.objects.all()))
    next_num = last + 1
    return f'{prefix}{next_num:04d}'


def get_seller_owner_type_filter(user):
    """
    Map role → product owner_type that this user may manage.
    Returns None for normal student sellers (no extra owner_type filter).
    """
    role = (getattr(user, 'user_role', '') or '').lower()

    if role in ('management', 'admin', 'campus_admin'):
        return 'MANAGEMENT'
    if role in ('alumni_assoc',) or getattr(user, 'is_officer', False):
        return 'ORGANIZATION'
    if role in ('organization', 'org'):
        return 'ORGANIZATION'
    return None


def _resolve_organization(order):
    """Map order seller → Organization safely without blocking evaluation."""
    seller = getattr(order, 'seller', None)

    # 1. First check if the seller account directly links to an organization
    if seller and getattr(seller, 'org_link_id', None):
        return seller.org_link

    # 2. Iterate items safely using a concrete list query
    items = list(order.items.select_related('product_variant__product__related_org').all())
    for item in items:
        product = getattr(item.product_variant, 'product', None)
        if product:
            if getattr(product, 'related_org_id', None):
                return product.related_org
            if getattr(product, 'owner_type', '') == 'ORGANIZATION' and hasattr(seller, 'org_link'):
                return seller.org_link

    return None


@transaction.atomic
def accrue_platform_fee_for_order(order):
    if (order.status or '').upper() != 'COMPLETED':
        return None

    # Idempotency check: check DB directly instead of relying on cached reverse attribute
    if PlatformFeeLine.objects.filter(order=order).exists():
        return PlatformFeeLine.objects.filter(order=order).first()

    org = _resolve_organization(order)
    if not org:
        return None  # Personal sellers — no platform fee

    today = timezone.localdate()

    # Select ledger with select_for_update to avoid race conditions
    ledger = (
        OrganizationPlatformLedger.objects
        .select_for_update()
        .filter(organization=org, status__in=['OPEN', 'DUE'])
        .order_by('-cycle_start')
        .first()
    )

    if not ledger:
        ledger = OrganizationPlatformLedger.objects.create(
            organization=org,
            cycle_start=today,
            cycle_due=today + timedelta(days=30),
            status='OPEN',
            accumulated_sales=Decimal('0.00'),
            accumulated_fee=Decimal('0.00'),
        )
    elif ledger.cycle_due < today and ledger.status == 'OPEN':
        ledger.status = 'DUE'
        ledger.save(update_fields=['status'])

    amount = Decimal(str(order.total_amount or 0))
    fee = (amount * PLATFORM_FEE_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    line = PlatformFeeLine.objects.create(
        ledger=ledger,
        order=order,
        order_amount=amount,
        fee_amount=fee,
    )

    ledger.accumulated_sales = (ledger.accumulated_sales or Decimal('0.00')) + amount
    ledger.accumulated_fee = (ledger.accumulated_fee or Decimal('0.00')) + fee
    ledger.save(update_fields=['accumulated_sales', 'accumulated_fee'])

    return line