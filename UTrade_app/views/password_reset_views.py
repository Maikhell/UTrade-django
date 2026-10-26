import logging
import re

from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from ..models import User
from ..utils import is_pending_verification, needs_google_completion, send_otp_email
from .otplink_views import MAX_OTP_ATTEMPTS, _mask_email, _resend_wait

logger = logging.getLogger(__name__)

# How long the "new password" page stays open after the code is verified
RESET_WINDOW_SECONDS = 15 * 60
SESSION_KEYS = ('pr_user_id', 'pr_verified_user_id', 'pr_verified_at')


def _clear_reset_session(request):
    for key in SESSION_KEYS:
        request.session.pop(key, None)


# Wrong-code counter lives in the cache and is tied to the account, not the browser
# session, so starting a new session doesn't hand out fresh guesses.
def _attempts_key(user):
    return f'pr_attempts:{user.pk}'


def _get_attempts(user):
    return cache.get(_attempts_key(user), 0)


def _bump_attempts(user):
    key = _attempts_key(user)
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, RESET_WINDOW_SECONDS)
        return 1


def _clear_attempts(user):
    cache.delete(_attempts_key(user))


def _eligible(user):
    """Google sign-ups that never finished setup have no password to reset."""
    if needs_google_completion(user):
        return False
    return user.is_active or is_pending_verification(user)


# =============================================================================
# Step 1: student number + email
# =============================================================================
def forgot_password(request):
    if request.method != 'POST':
        return render(request, 'UTrade_app/accounts/forgot_password.html')

    student_no = (request.POST.get('student_no') or '').strip()
    email = (request.POST.get('email') or '').strip().lower()
    errors = {}

    if not re.fullmatch(r'\d{9}', student_no):
        errors['student_no'] = ['Student number must be exactly 9 digits.']
    try:
        validate_email(email)
    except ValidationError:
        errors['email'] = ['Enter a valid email address.']

    ctx = {'student_no': student_no, 'email': email, 'errors': errors}
    if errors:
        return render(request, 'UTrade_app/accounts/forgot_password.html', ctx)

    user = User.objects.filter(
        student_no__iexact=student_no, email__iexact=email
    ).first()

    if not user or not _eligible(user):
        ctx['error'] = (
            "We couldn't find an account that matches both the student number and the email."
        )
        return render(request, 'UTrade_app/accounts/forgot_password.html', ctx)

    wait = _resend_wait(user)
    if wait > 0 and not user.otp_code:
        ctx['error'] = f"Please wait {wait} seconds before requesting another code."
        return render(request, 'UTrade_app/accounts/forgot_password.html', ctx)

    # A code sent within the last minute is still valid: reuse it instead of emailing again
    if not (wait > 0 and user.otp_code):
        try:
            send_otp_email(user, purpose='reset')
        except Exception:
            logger.exception("Password reset OTP failed for user_id=%s", user.id)
            ctx['error'] = "We couldn't send the code right now. Please try again shortly."
            return render(request, 'UTrade_app/accounts/forgot_password.html', ctx)
        _clear_attempts(user)

    _clear_reset_session(request)
    request.session['pr_user_id'] = user.id
    return redirect('password_reset_verify')


# =============================================================================
# Step 2: enter the emailed code
# =============================================================================
def _render_verify(request, user, error=None, notice=None, otp_invalid=False):
    attempts = _get_attempts(user)
    locked = attempts >= MAX_OTP_ATTEMPTS or not user.otp_code
    expires_in = 0
    if user.otp_code and user.otp_expiry:
        expires_in = max(0, int((user.otp_expiry - timezone.now()).total_seconds()))

    return render(request, 'UTrade_app/accounts/reset_verify.html', {
        'masked_email': _mask_email(user.email),
        'attempts_left': max(0, MAX_OTP_ATTEMPTS - attempts),
        'attempts_used': attempts,
        'max_attempts': MAX_OTP_ATTEMPTS,
        'locked': locked,
        'expires_in': expires_in,
        'resend_wait': _resend_wait(user),
        'error': error,
        'notice': notice,
        'otp_invalid': otp_invalid,
    })


def password_reset_verify(request):
    uid = request.session.get('pr_user_id')
    user = User.objects.filter(pk=uid).first() if uid else None

    if user is None:
        messages.error(request, "Please enter your student number and email first.")
        return redirect('forgot_password')

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
            send_otp_email(user, purpose='reset')
        except Exception:
            logger.exception("Password reset OTP resend failed for user_id=%s", user.id)
            return _render_verify(
                request, user,
                error="We couldn't send the code right now. Please try again shortly.",
            )
        _clear_attempts(user)
        user.refresh_from_db()
        return _render_verify(request, user, notice="A new code has been sent to your email.")

    # ---------- Verify ----------
    attempts = _get_attempts(user)
    if attempts >= MAX_OTP_ATTEMPTS or not user.otp_code:
        return _render_verify(
            request, user,
            error="Too many incorrect attempts. Please request a new code.",
            otp_invalid=True,
        )

    otp_entered = re.sub(r'\D', '', request.POST.get('otp', ''))

    if len(otp_entered) != 6:
        return _render_verify(
            request, user, error="Please enter the full 6-digit code.", otp_invalid=True
        )

    if not user.otp_expiry or user.otp_expiry <= timezone.now():
        return _render_verify(
            request, user,
            error="This code has expired. Please request a new one.",
            otp_invalid=True,
        )

    if constant_time_compare(user.otp_code, otp_entered):
        _clear_attempts(user)
        user.otp_code = None
        user.save(update_fields=['otp_code'])

        request.session.pop('pr_user_id', None)
        request.session['pr_verified_user_id'] = user.id
        request.session['pr_verified_at'] = timezone.now().timestamp()
        return redirect('password_reset_new')

    # Wrong code
    attempts = _bump_attempts(user)
    if attempts >= MAX_OTP_ATTEMPTS:
        user.otp_code = None  # destroy the code so it can't be guessed further
        user.save(update_fields=['otp_code'])
        return _render_verify(
            request, user,
            error="Too many incorrect attempts. Please request a new code.",
            otp_invalid=True,
        )

    remaining = MAX_OTP_ATTEMPTS - attempts
    return _render_verify(
        request, user,
        error=f"Incorrect code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
        otp_invalid=True,
    )


# =============================================================================
# Step 3: choose a new password
# =============================================================================
def _verified_user(request):
    uid = request.session.get('pr_verified_user_id')
    ts = request.session.get('pr_verified_at')
    if not uid or not ts:
        return None
    if timezone.now().timestamp() - ts > RESET_WINDOW_SECONDS:
        return None
    return User.objects.filter(pk=uid).first()


def password_reset_new(request):
    user = _verified_user(request)
    if user is None:
        _clear_reset_session(request)
        messages.error(request, "Your reset session expired. Please start again.")
        return redirect('forgot_password')

    template = 'UTrade_app/accounts/reset_new_password.html'
    ctx = {'masked_email': _mask_email(user.email), 'errors': {}}

    if request.method != 'POST':
        return render(request, template, ctx)

    password1 = request.POST.get('password1') or ''
    password2 = request.POST.get('password2') or ''
    errors = {}

    if not password1:
        errors['password1'] = ['Please enter a new password.']
    else:
        try:
            validate_password(password1, user)
        except ValidationError as exc:
            errors['password1'] = list(exc.messages)
        else:
            if user.has_usable_password() and user.check_password(password1):
                errors['password1'] = ["Choose a password you haven't used before."]

    if password1 != password2:
        errors['password2'] = ['Passwords do not match.']

    if errors:
        ctx['errors'] = errors
        return render(request, template, ctx)

    # The code proved they own this email, so also finish an unverified registration
    was_pending = is_pending_verification(user)

    user.set_password(password1)
    update_fields = ['password']
    if not user.is_email_verified:
        user.is_email_verified = True
        update_fields.append('is_email_verified')
    if was_pending:
        user.is_active = True
        update_fields.append('is_active')
    user.save(update_fields=update_fields)

    _clear_reset_session(request)
    messages.success(request, "Password updated. You can now sign in with your new password.")
    return redirect('user.login')