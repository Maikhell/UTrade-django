import uuid

from django.db import models
from django.conf import settings


class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Delivered', 'Delivered'),
        ('Accepted', 'Accepted'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
        ('Rejected', 'Rejected'),
    ]

    PAYMENT_METHODS = [
        ('GCASH', 'GCash (Online)'),
        ('COP', 'Cash on Pickup'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    CANCELLATION_CHOICES = [
        ('Changed mind', 'Changed my mind'),
        ('Found better price', 'Found a better price'),
        ('Accidental order', 'Accidental order'),
        ('Seller not responding', 'Seller is not responding'),
        ('Other', 'Other'),
    ]
    REJECTION_CHOICES = [
        ('Out of stock', 'Item(s) out of stock'),
        ('Pricing/Listing error', 'Pricing or product listing error'),
        ('Other', 'Other'),
    ]

    # Human-readable unique ID, e.g. UT261020-000123 (filled in on first save)
    order_number = models.CharField(
        max_length=24, unique=True, null=True, blank=True, editable=False
    )
    # Shared by all sibling orders created from one checkout
    checkout_batch = models.UUIDField(
        null=True, blank=True, db_index=True, editable=False
    )

    rejection_reason = models.CharField(
        max_length=100, choices=REJECTION_CHOICES, null=True, blank=True
    )
    cancellation_reason = models.CharField(
        max_length=100, choices=CANCELLATION_CHOICES, null=True, blank=True
    )
    cancellation_note = models.TextField(null=True, blank=True)

    meetup_location = models.CharField(max_length=255, blank=True, null=True)
    pickup_time = models.DateTimeField(blank=True, null=True)
    seller_note = models.TextField(blank=True, null=True)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='seller_orders', null=True, blank=True
    )
    pickup_location = models.CharField(max_length=255, blank=True, null=True)
    buyer_note = models.TextField(blank=True, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_rated(self):
        return self.order_reviews.exists()

    def _build_order_number(self):
        return f"UT{self.created_at:%y%m%d}-{self.pk:06d}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.order_number:
            self.order_number = self._build_order_number()
            type(self).objects.filter(pk=self.pk).update(order_number=self.order_number)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product_variant = models.ForeignKey(
        'UTrade_app.ProductVariant',
        on_delete=models.SET_NULL,
        null=True
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        if self.product_variant and self.product_variant.product:
            return f"{self.quantity}x {self.product_variant.product.name}"
        return f"{self.quantity}x Deleted Product"

    def get_cost(self):
        return self.price * self.quantity


class SystemLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    item_type = models.CharField(max_length=50)
    item_name = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} - {self.action} {self.item_type} ({self.timestamp})"