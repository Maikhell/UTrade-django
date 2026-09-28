from .models import SystemLog, Product, StagedProduct
import random
import re
import logging
from datetime import timedelta

from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def log_action(user, action, item_type, item_name, details=""):
    SystemLog.objects.create(
        user=user,
        action=action,
        item_type=item_type,
        item_name=item_name,
        details=details,
    )


def send_otp_email(user):
    """
    Generate a 6-digit OTP, store expiry on the user, email it to user.email.
    Raises on missing email or SMTP failure so the caller can show a message.
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
    email_from = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or settings.EMAIL_HOST_USER

    try:
        sent = send_mail(
            subject,
            message,
            email_from,
            [recipient],
            fail_silently=False,  # surface SMTP errors in Railway logs
        )
        logger.info('OTP email sent to %s (sent=%s)', recipient, sent)
        return sent
    except Exception:
        logger.exception('OTP email FAILED for user_id=%s email=%s', user.id, recipient)
        raise


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