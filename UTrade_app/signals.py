from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Cart, Order
from .utils import accrue_platform_fee_for_order


@receiver(post_save, sender=User)
def create_user_cart(sender, instance, created, **kwargs):
    if created:
        Cart.objects.create(user=instance)


@receiver(post_save, sender=Order)
def trigger_platform_fee_accrual(sender, instance, created, **kwargs):
    # Only run on status 'Completed'
    if (instance.status or '').upper() == 'COMPLETED':
        # Prevent recursion if order is saved again inside accrue_platform_fee_for_order
        if getattr(instance, '_accruing_fee', False):
            return
        
        instance._accruing_fee = True
        try:
            accrue_platform_fee_for_order(instance)
        finally:
            instance._accruing_fee = False