"""
UTrade_app/alumni_middleware.py

Safety net: if an alumnus whose access has ended is still signed in, this
deactivates the account and signs them out on their next request. It works even if the
daily deactivate_expired_alumni command has not run yet.

Add to MIDDLEWARE in settings.py, AFTER AuthenticationMiddleware and MessageMiddleware:

    'UTrade_app.alumni_middleware.AlumniExpiryMiddleware',
"""
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


class AlumniExpiryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and getattr(user, 'is_alumni', False):
            expires = getattr(user, 'alumni_expires_at', None)
            if expires and expires < timezone.localdate():
                user.is_active = False
                user.save(update_fields=['is_active'])
                logout(request)
                # The login page shows a pop-up when it sees ?alumni_expired=1
                return redirect(reverse('user.login') + '?alumni_expired=1')
        return self.get_response(request)