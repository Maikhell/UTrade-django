from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from .utils import needs_google_completion

COMPLETE_PROFILE_PATH = '/complete-google-profile/'


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        current_path = request.path

        # Static / media / admin
        static_url = getattr(settings, 'STATIC_URL', '/static/') or '/static/'
        media_url = getattr(settings, 'MEDIA_URL', '/media/') or '/media/'

        if current_path.startswith(static_url):
            return self.get_response(request)

        if current_path.startswith('/admin/'):
            return self.get_response(request)

        if media_url and current_path.startswith(media_url):
            return self.get_response(request)

        # Google sign-ups must finish the setup page (student number, password, OTP)
        # before they can use the rest of the site. Based on the account itself,
        # not a session flag, so they can't skip it by navigating away.
        user = request.user
        if user.is_authenticated and needs_google_completion(user):
            allowed = (COMPLETE_PROFILE_PATH, '/accounts/', '/logout/')
            if any(current_path.startswith(p) for p in allowed):
                return self.get_response(request)
            return redirect('complete_google_profile')

        # Prefixes that must stay public (allauth Google OAuth lives under /accounts/)
        exempt_prefixes = (
            '/accounts/',   # django-allauth (Google login + callback)
            '/login/',
            '/register/',
            '/verify-email/',
            '/verify-otp/',
        )

        if any(current_path.startswith(p) for p in exempt_prefixes):
            return self.get_response(request)

        # Exact named URLs (optional extra safety)
        try:
            exempt_exact = {
                reverse('user.login'),
                reverse('user.register'),
                reverse('landingpage'),
                reverse('verify_otp'),
            }
        except Exception:
            exempt_exact = set()

        if current_path in exempt_exact:
            return self.get_response(request)

        # Everything else requires login
        if not user.is_authenticated:
            return redirect('landingpage')

        return self.get_response(request)