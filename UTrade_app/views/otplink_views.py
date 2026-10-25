# Django Core Imports
import logging
import math
import re
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from ..models import User
from ..utils import send_otp_email, needs_google_completion

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


def _issue_code(request, user, prefix):
    """
    Email a fresh OTP and reset this flow's attempt counter.
    prefix: 'otp' (email registration) or 'g_otp' (Google setup page).
    Returns an error message, or None on success.
    """
    try:
        send_otp_email(user)
    except Exception:
        logger.exception("Could not send OTP to user_id=%s", user.id)
        return "We couldn't send the code right now. Please press Resend code in a moment."
    request.session[f'{prefix}_sent'] = True
    request.session[f'{prefix}_attempts'] = 0
    return None


def _auto_send(request, user, prefix):
    """
    First visit in this session: send a code unless a still-valid one exists.
    Returns (error, notice).
    """
    if request.session.get(f'{prefix}_sent'):
        return None, None

    if user.otp_code and user.otp_expiry and user.otp_expiry > timezone.now():
        request.session[f'{prefix}_sent'] = True  # e.g. just registered: already emailed
        return None, None

    error = _issue_code(request, user, prefix)
    if error:
        return error, None
    return None, "We've sent a verification code to your email."


# =============================================================================
# Email registration: verify the emailed OTP
# =============================================================================
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
        messages.error(
            request,
            "Your verification session expired. Please sign in to continue verifying your email.",
        )
        return redirect('user.login')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.pop('pending_user_id', None)
        return redirect('user.register')

    # ---------- GET: make sure they have a code ----------
    if request.method != 'POST':
        error, notice = _auto_send(request, user, 'otp')
        user.refresh_from_db()
        return _render_verify(request, user, error=error, notice=notice)

    action = request.POST.get('action', 'verify')

    # ---------- Resend ----------
    if action == 'resend':
        wait = _resend_wait(user)
        if wait > 0:
            return _render_verify(
                request, user,
                error=f"Please wait {wait} seconds before requesting a new code.",
            )
        error = _issue_code(request, user, 'otp')
        user.refresh_from_db()
        if error:
            return _render_verify(request, user, error=error)
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

        for key in ('pending_user_id', 'otp_attempts', 'otp_sent'):
            request.session.pop(key, None)

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


# =============================================================================
# Google sign-up: OTP + student number + password, all on one page
# =============================================================================
def _render_complete(request, user, student_no='', errors=None, error=None,
                     notice=None, otp_invalid=False):
    attempts = request.session.get('g_otp_attempts', 0)
    locked = attempts >= MAX_OTP_ATTEMPTS or not user.otp_code
    expires_in = 0
    if user.otp_code and user.otp_expiry:
        expires_in = max(0, int((user.otp_expiry - timezone.now()).total_seconds()))

    return render(request, 'UTrade_app/accounts/complete_google_profile.html', {
        'masked_email': _mask_email(user.email),
        'student_no': student_no,
        'errors': errors or {},
        'error': error,
        'notice': notice,
        'otp_invalid': otp_invalid,
        'attempts_left': max(0, MAX_OTP_ATTEMPTS - attempts),
        'attempts_used': attempts,
        'max_attempts': MAX_OTP_ATTEMPTS,
        'locked': locked,
        'expires_in': expires_in,
        'resend_wait': _resend_wait(user),
    })


@login_required
def complete_google_profile(request):
    user = User.objects.get(pk=request.user.pk)

    # Already finished (or never a Google sign-up): nothing to do here
    if not needs_google_completion(user):
        request.session.pop('complete_google_signup', None)
        return redirect('product.list')

    # ---------- GET: make sure they have a code ----------
    if request.method != 'POST':
        error, notice = _auto_send(request, user, 'g_otp')
        user.refresh_from_db()
        return _render_complete(request, user, error=error, notice=notice)

    action = request.POST.get('action', 'verify')
    student_no = (request.POST.get('student_no') or '').strip()

    # ---------- Resend ----------
    if action == 'resend':
        wait = _resend_wait(user)
        if wait > 0:
            return _render_complete(
                request, user, student_no=student_no,
                error=f"Please wait {wait} seconds before requesting a new code.",
            )
        error = _issue_code(request, user, 'g_otp')
        user.refresh_from_db()
        if error:
            return _render_complete(request, user, student_no=student_no, error=error)
        return _render_complete(
            request, user, student_no=student_no,
            notice="A new code has been sent to your email.",
        )

    # ---------- Verify + save ----------
    errors = {}

    # Student number: exactly 9 digits (same rule as the register page)
    if not re.fullmatch(r'\d{9}', student_no):
        errors['student_no'] = ['Student number must be exactly 9 digits.']
    else:
        entry_year = int(student_no[:4])
        current_year = timezone.now().year
        if entry_year > current_year:
            errors['student_no'] = ['Entry year cannot be in the future.']
        elif current_year - entry_year > 6:
            errors['student_no'] = ['This student number is too old for registration.']
        elif User.objects.filter(student_no__iexact=student_no).exclude(pk=user.pk).exists():
            errors['student_no'] = ['An account with this student number already exists.']

    # Password
    password1 = request.POST.get('password1') or ''
    password2 = request.POST.get('password2') or ''
    if not password1:
        errors['password1'] = ['Please enter a password.']
    else:
        try:
            validate_password(password1, user)
        except ValidationError as exc:
            errors['password1'] = list(exc.messages)
    if password1 != password2:
        errors['password2'] = ['Passwords do not match.']

    # OTP (attempts are counted even when other fields have errors)
    attempts = request.session.get('g_otp_attempts', 0)
    otp_error = None
    otp_ok = False

    if attempts >= MAX_OTP_ATTEMPTS:
        otp_error = "Too many incorrect attempts. Please request a new code."
    elif not user.otp_code:
        otp_error = "Please request a new code."
    else:
        otp_entered = re.sub(r'\D', '', request.POST.get('otp', ''))
        if len(otp_entered) != 6:
            otp_error = "Please enter the full 6-digit code."
        elif not user.otp_expiry or user.otp_expiry <= timezone.now():
            otp_error = "This code has expired. Please request a new one."
        elif constant_time_compare(user.otp_code, otp_entered):
            otp_ok = True
        else:
            attempts += 1
            request.session['g_otp_attempts'] = attempts
            if attempts >= MAX_OTP_ATTEMPTS:
                user.otp_code = None  # invalidate so it can't be guessed further
                user.save(update_fields=['otp_code'])
                otp_error = "Too many incorrect attempts. Please request a new code."
            else:
                remaining = MAX_OTP_ATTEMPTS - attempts
                otp_error = (
                    f"Incorrect code. {remaining} attempt{'s' if remaining != 1 else ''} remaining."
                )

    if errors or not otp_ok:
        return _render_complete(
            request, user, student_no=student_no, errors=errors,
            error=otp_error, otp_invalid=bool(otp_error),
        )

    # ---------- Everything checks out ----------
    try:
        with transaction.atomic():
            user.student_no = student_no
            user.set_password(password1)
            user.is_email_verified = True
            user.is_active = True
            user.otp_code = None
            user.save()
    except IntegrityError:
        errors['student_no'] = ['An account with this student number already exists.']
        return _render_complete(request, user, student_no=student_no, errors=errors)

    # Changing the password invalidates the session unless we refresh its hash
    update_session_auth_hash(request, user)

    for key in ('g_otp_attempts', 'g_otp_sent', 'complete_google_signup'):
        request.session.pop(key, None)

    messages.success(request, "Your account is set up. Welcome to UTrade!")
    return redirect('product.list')