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
    """
    Automatically accrue 3% platform fee and update or create the 
    OrganizationPlatformLedger whenever an order reaches COMPLETED status.
    """
    if (instance.status or '').upper() == 'COMPLETED':
        accrue_platform_fee_for_order(instance)