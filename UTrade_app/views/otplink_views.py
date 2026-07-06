# Django Core Imports
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import login
from ..models import User 

def verify_otp(request):
    print("--- DEBUG SESSION ---")
    print(f"All Session Keys: {request.session.keys()}")
    print(f"User ID found: {request.session.get('pending_user_id')}")

    user_id = request.session.get('pending_user_id')

    if not user_id:
        messages.error(request, "Registration session expired. Please register again.")
        return redirect('user.register')

    if request.method == 'POST':
        otp_entered = request.POST.get('otp')
        
        try:
            user = User.objects.get(id=user_id)
            
            if user.otp_code == otp_entered and user.otp_expiry > timezone.now():
                user.status = 'unverified' 
                user.is_active = True
                user.otp_code = None 
                user.save()
                
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                
                if 'pending_user_id' in request.session:
                    del request.session['pending_user_id']
                
                messages.success(request, "Email verified successfully! Welcome to UTrade.")
                
                return redirect('product.list')
            else:
                messages.error(request, "Invalid or expired OTP code.")
                
        except User.DoesNotExist:
            return redirect('user.register')

    return render(request, 'UTrade_app/accounts/verify.html')