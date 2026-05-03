from .models import SystemLog
import random
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

def log_action(user, action, item_type, item_name, details=""):
    SystemLog.objects.create(
        user=user,
        action=action,
        item_type=item_type,
        item_name=item_name,
        details=details
    )
def send_otp_email(user):
    """
    Generates a 6-digit OTP, sets expiry, and sends it to the user's CVSU email.
    """
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_expiry = timezone.now() + timedelta(minutes=10)
    user.save()

    subject = 'Verify your UTrade Account'
    message = f'Your verification code is: {otp}. It expires in 10 minutes.'
    email_from = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    
    send_mail(subject, message, email_from, recipient_list)