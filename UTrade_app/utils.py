from .models import SystemLog
import random
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import Max
from .models import Product, StagedProduct
import re

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
    
def generate_next_product_code(model_cls=None):
    """
    Format: UTR-YYYY-####  (zero-padded, auto-increment per year)
    Looks at Product (+ StagedProduct if you pass both via a shared sequence).
    """  

    year = timezone.now().year
    prefix = f'UTR-{year}-'

    def max_seq(qs):
        codes = qs.filter(product_code__startswith=prefix).values_list(
            'product_code', flat=True
        )
        best = 0
        for code in codes:
            m = re.search(r'(\d+)$', code or '')
            if m:
                best = max(best, int(m.group(1)))
        return best

    last = max(max_seq(Product.objects.all()), max_seq(StagedProduct.objects.all()))
    next_num = last + 1
    return f'{prefix}{next_num:04d}'