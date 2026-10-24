# Django Core Imports
import logging
import math
import re
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from ..models import User
from ..utils import send_otp_email

logger = logging.getLogger(__name__)

MAX_OTP_ATTEMPTS = 5
OTP_LIFETIME = timedelta(minutes=10)   # must match send_otp_email()
RESEND_COOLDOWN = 60                   # seconds


def _mask_email(email):
    local, _, domain = (email or '').partition('@')
    if not domain:
        return email or ''
    return f"{local[:2]}{'*' * max(len(local) - 2, 1)}@{domain}"


def _resend_wait(user):
    """Seconds left before another code may be requested."""
    if not user.otp_expiry:
        return 0
    sent_at = user.otp_expiry - OTP_LIFETIME
    elapsed = (timezone.now() - sent_at).total_seconds()
    return min(RESEND_COOLDOWN, max(0, math.ceil(RESEND_COOLDOWN - elapsed)))


def _render_verify(request, user, error=None, notice=None):
    attempts = request.session.get('otp_attempts', 0)
    locked = attempts >= MAX_OTP_ATTEMPTS or not user.otp_code
    expires_in = 0
    if user.otp_code and user.otp_expiry:
        expires_in = max(0, int((user.otp_expiry - timezone.now()).total_seconds()))

    return render(request, 'UTrade_app/accounts/verify.html', {
        'masked_email': _mask_email(user.email),
        'attempts_left': max(0, MAX_OTP_ATTEMPTS - attempts),
        'attempts_used': attempts,
        'max_attempts': MAX_OTP_ATTEMPTS,
        'locked': locked,
        'expires_in': expires_in,
        'resend_wait': _resend_wait(user),
        'error': error,
        'notice': notice,
    })


def verify_otp(request):
    user_id = request.session.get('pending_user_id')

    if not user_id:
        messages.error(request, "Registration session expired. Please register again.")
        return redirect('user.register')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.pop('pending_user_id', None)
        return redirect('user.register')

    if request.method != 'POST':
        return _render_verify(request, user)

    action = request.POST.get('action', 'verify')

    # ---------- Resend ----------
    if action == 'resend':
        wait = _resend_wait(user)
        if wait > 0:
            return _render_verify(
                request, user,
                error=f"Please wait {wait} seconds before requesting a new code.",
            )
        try:
            send_otp_email(user)
        except Exception:
            logger.exception("Resend OTP failed for user_id=%s", user.id)
            return _render_verify(
                request, user,
                error="We couldn't send the code right now. Please try again shortly.",
            )
        request.session['otp_attempts'] = 0
        user.refresh_from_db()
        return _render_verify(request, user, notice="A new code has been sent to your email.")

    # ---------- Verify ----------
    attempts = request.session.get('otp_attempts', 0)

    if attempts >= MAX_OTP_ATTEMPTS or not user.otp_code:
        return _render_verify(
            request, user,
            error="Too many incorrect attempts. Please request a new code.",
        )

    otp_entered = re.sub(r'\D', '', request.POST.get('otp', ''))

    if len(otp_entered) != 6:
        return _render_verify(request, user, error="Please enter the full 6-digit code.")

    if not user.otp_expiry or user.otp_expiry <= timezone.now():
        return _render_verify(
            request, user,
            error="This code has expired. Please request a new one.",
        )

    if constant_time_compare(user.otp_code, otp_entered):
        user.status = 'unverified'
        user.is_active = True
        user.is_email_verified = True
        user.otp_code = None
        user.save()

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        request.session.pop('pending_user_id', None)
        request.session.pop('otp_attempts', None)

        messages.success(request, "Email verified successfully! Welcome to UTrade.")
        return redirect('product.list')

    # Wrong code
    attempts += 1
    request.session['otp_attempts'] = attempts

    if attempts >= MAX_OTP_ATTEMPTS:
        user.otp_code = None  # invalidate the code so it can't be guessed further
        user.save(update_fields=['otp_code'])
        return _render_verify(
            request, user,
            error="Too many incorrect attempts. Please request a new code.",
        )

    remaining = MAX_OTP_ATTEMPTS - attempts
    return _render_verify(
        request, user,
        error=f"Incorrect code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
    )