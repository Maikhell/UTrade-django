# UTrade_app/adapters.py
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()
ALLOWED_EMAIL_DOMAIN = 'cvsu.edu.ph'


def _is_cvsu_email(email: str) -> bool:
    email = (email or '').strip().lower()
    return email.endswith(f'@{ALLOWED_EMAIL_DOMAIN}')


def _needs_profile_completion(user) -> bool:
    student_no = getattr(user, 'student_no', '') or ''
    status = (getattr(user, 'status', '') or '').lower()
    return (
        not student_no
        or str(student_no).startswith('TMP-')
        or status in ('unverified', 'pending', '')
    )


class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        user = request.user
        if not user.is_authenticated:
            return reverse('product.list')

        if request.session.get('complete_google_signup', False) or _needs_profile_completion(user):
            try:
                return reverse('complete_google_profile')
            except Exception:
                return reverse('user.profile')

        return reverse('product.list')


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = (
            sociallogin.account.extra_data.get('email')
            or getattr(sociallogin.user, 'email', '')
            or ''
        ).strip().lower()

        if not _is_cvsu_email(email):
            messages.error(
                request,
                'Only CVSU email addresses (@cvsu.edu.ph) are allowed. '
                'Please sign in with your institutional Google account.',
            )
            raise ImmediateHttpResponse(redirect('user.login'))

        # Already logged-in social user object with PK
        if sociallogin.user.id:
            # Reactivate if an older Google signup left them inactive
            if not sociallogin.user.is_active:
                sociallogin.user.is_active = True
                sociallogin.user.save(update_fields=['is_active'])
            return

        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            if not _is_cvsu_email(existing.email or ''):
                messages.error(
                    request,
                    'Only CVSU email addresses (@cvsu.edu.ph) are allowed.',
                )
                raise ImmediateHttpResponse(redirect('user.login'))

            # Critical: inactive local accounts fail social login
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
        return _is_cvsu_email(email)

    def save_user(self, request, sociallogin, form=None):
        email = (
            sociallogin.account.extra_data.get('email')
            or getattr(sociallogin.user, 'email', '')
            or ''
        )
        if not _is_cvsu_email(email):
            messages.error(
                request,
                'Only CVSU email addresses (@cvsu.edu.ph) are allowed.',
            )
            raise ImmediateHttpResponse(redirect('user.login'))

        user = super().save_user(request, sociallogin, form=form)

        # Allow login; incomplete profile is enforced by status + middleware
        changed = False
        if not user.is_active:
            user.is_active = True
            changed = True

        if not getattr(user, 'student_no', None):
            user.student_no = f'TMP-{uuid.uuid4().hex[:10]}'
            changed = True

        if not getattr(user, 'status', None) or user.status == '':
            user.status = 'unverified'
            changed = True

        if not getattr(user, 'user_role', None):
            user.user_role = 'student'
            changed = True

        if changed:
            user.save()

        request.session['pending_user_id'] = user.id
        request.session['complete_google_signup'] = True
        request.session.modified = True

        return user