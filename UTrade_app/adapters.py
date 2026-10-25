# UTrade_app/adapters.py
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import get_user_model
import uuid

from .utils import is_allowed_email, is_pending_verification, needs_google_completion

User = get_user_model()

EMAIL_NOT_ALLOWED_MSG = (
    'Only Gmail or CvSU (@cvsu.edu.ph) email addresses are allowed. '
    'Please sign in with one of those Google accounts.'
)


class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        user = request.user
        if not user.is_authenticated:
            return reverse('product.list')

        # New Google sign-ups must set a student number + password and verify the OTP first
        if needs_google_completion(user):
            return reverse('complete_google_profile')

        return reverse('product.list')


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = (
            sociallogin.account.extra_data.get('email')
            or getattr(sociallogin.user, 'email', '')
            or ''
        ).strip().lower()

        if not is_allowed_email(email):
            messages.error(request, EMAIL_NOT_ALLOWED_MSG)
            raise ImmediateHttpResponse(redirect('user.login'))

        # Already-linked social account
        if sociallogin.user.id:
            # Reactivate if an older Google signup left them inactive
            if not sociallogin.user.is_active:
                sociallogin.user.is_active = True
                sociallogin.user.save(update_fields=['is_active'])
            return

        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            if not is_allowed_email(existing.email or ''):
                messages.error(request, EMAIL_NOT_ALLOWED_MSG)
                raise ImmediateHttpResponse(redirect('user.login'))

            # Registered with email but never verified: finish the OTP step first,
            # Google sign-in must not skip it.
            if is_pending_verification(existing):
                request.session['pending_user_id'] = existing.id
                request.session.pop('otp_sent', None)
                request.session.pop('otp_attempts', None)
                messages.info(
                    request,
                    'Please verify your email first to finish creating your account.',
                )
                raise ImmediateHttpResponse(redirect('verify_otp'))

            # Inactive local accounts fail social login
            if not existing.is_active:
                existing.is_active = True
                existing.save(update_fields=['is_active'])

            sociallogin.connect(request, existing)

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        email = (data.get('email') or getattr(user, 'email', '') or '').lower()
        user.email = email

        if data.get('given_name'):
            user.first_name = str(data.get('given_name'))[:30]
        if data.get('family_name'):
            user.last_name = str(data.get('family_name'))[:150]

        if not getattr(user, 'username', None):
            base = (email.split('@')[0] if email else 'user')[:20]
            user.username = base

        return user

    def is_auto_signup_allowed(self, request, sociallogin):
        email = (
            sociallogin.account.extra_data.get('email')
            or getattr(sociallogin.user, 'email', '')
            or ''
        )
        return is_allowed_email(email)

    def save_user(self, request, sociallogin, form=None):
        email = (
            sociallogin.account.extra_data.get('email')
            or getattr(sociallogin.user, 'email', '')
            or ''
        )
        if not is_allowed_email(email):
            messages.error(request, EMAIL_NOT_ALLOWED_MSG)
            raise ImmediateHttpResponse(redirect('user.login'))

        user = super().save_user(request, sociallogin, form=form)

        changed = False
        if not user.is_active:
            user.is_active = True
            changed = True

        # Placeholder until the user enters their real student number on the setup page
        if not getattr(user, 'student_no', None):
            user.student_no = f'TMP-{uuid.uuid4().hex[:10]}'
            changed = True

        if not getattr(user, 'status', None) or user.status == '':
            user.status = 'unverified'
            changed = True

        if not getattr(user, 'user_role', None):
            user.user_role = 'student'
            changed = True

        # Google proves the address, but we still verify by OTP on the setup page
        if user.is_email_verified:
            user.is_email_verified = False
            changed = True

        if changed:
            user.save()

        request.session['complete_google_signup'] = True
        request.session.modified = True

        return user