from django.urls import reverse
from django.shortcuts import redirect
from django.conf import settings


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
        if not request.user.is_authenticated:
            return redirect('landingpage')

        if request.user.is_authenticated:
            complete_paths = (
                '/profile/', '/userprofile/', '/complete-google-profile/',
                '/logout/', '/accounts/logout/',
            )

            # If this is a fresh Google signup, guide them to the profile page once.
            # Once they reach a complete path, clear the flag so they can navigate the site normally.
            if request.session.get('complete_google_signup', False):
                if any(current_path.startswith(p) for p in complete_paths):
                    request.session.pop('complete_google_signup', None)
                    request.session.modified = True
                else:
                    try:
                        return redirect('complete_google_profile')
                    except Exception:
                        return redirect('user.profile')

        return self.get_response(request)
