from django.urls import reverse
from django.shortcuts import redirect
from django.conf import settings

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        current_path = request.path
        
        if current_path.startswith(settings.STATIC_URL) or current_path.startswith('/admin/'):
            return self.get_response(request)
        
        if settings.MEDIA_URL and current_path.startswith(settings.MEDIA_URL):
            return self.get_response(request)
        exempt_urls = [
            reverse('user.login'),
            reverse('user.register'),
            reverse('landingpage'),
            reverse('verify_otp'),  
        ]
        if not request.user.is_authenticated and current_path not in exempt_urls:
            return redirect('landingpage')
            
        return self.get_response(request)