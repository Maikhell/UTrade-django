from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta

PLATFORM_FEE_RATE = Decimal('0.03') 

class Organization(models.Model):
    name = models.CharField(max_length=50, unique=True) #"ITS"
    full_name = models.CharField(max_length=150)        #"Information Technology Society"
    course_code = models.CharField(max_length=20)       #"BSIT"
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='org_logos/', blank=True, null=True)
    approval_letter = models.ImageField(                 # ← new field
        upload_to='org_approval_letters/',
        blank=True,
        null=True,
        help_text='JPG/PNG only, max 10 MB'
    )
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.course_code})" 

class OrganizationPlatformLedger(models.Model):
    """One open cycle per organization (30 days from first completed sale in cycle)."""
    STATUS_OPEN = 'OPEN'
    STATUS_DUE = 'DUE'
    STATUS_PAID = 'PAID'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_DUE, 'Due'),
        (STATUS_PAID, 'Paid / Remitted'),
    ]

    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, related_name='fee_ledgers'
    )
    cycle_start = models.DateField()
    cycle_due = models.DateField()  # cycle_start + 30 days
    accumulated_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    accumulated_sales = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-cycle_start']

    def __str__(self):
        return f'{self.organization.name} {self.cycle_start} → {self.cycle_due} ({self.status})'

    @property
    def days_until_due(self):
        return (self.cycle_due - timezone.localdate()).days

    @property
    def is_warning(self):
        d = self.days_until_due
        return self.status != self.STATUS_PAID and 0 <= d <= 7

    @property
    def is_overdue(self):
        return self.status != self.STATUS_PAID and self.days_until_due < 0


class PlatformFeeLine(models.Model):
    """3% of each completed org order."""
    ledger = models.ForeignKey(
        OrganizationPlatformLedger, on_delete=models.CASCADE, related_name='lines'
    )
    order = models.OneToOneField(
        'Order', on_delete=models.CASCADE, related_name='platform_fee_line', null=True, blank=True
    )
    order_amount = models.DecimalField(max_digits=12, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)


class PlatformFeeRemittance(models.Model):
    ledger = models.OneToOneField(
        OrganizationPlatformLedger, on_delete=models.CASCADE, related_name='remittance'
    )
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()  # auto on record
    due_date = models.DateField()      # copy from ledger.cycle_due
    management_rep_name = models.CharField(max_length=120)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='recorded_remittances'
    )
    receipt_no = models.CharField(max_length=32, unique=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.receipt_no