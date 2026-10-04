from django.contrib import admin
from .models import (
    User,
    Category,
    Product,
    ProductVariant,
    Organization,
    OrganizationPlatformLedger,
    PlatformFeeLine,
    PlatformFeeRemittance,
)


# ---------- existing ProductVariant inline ----------
class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ['variant_name', 'price', 'stocks']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductVariantInline]
    list_display = ['name', 'seller', 'category', 'status']
    list_filter = ['status', 'category']
    search_fields = ['name', 'description']


# ---------- Organization ----------
@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'full_name', 'course_code', 'date_created']
    search_fields = ['name', 'full_name', 'course_code']
    list_filter = ['course_code', 'date_created']
    readonly_fields = ['date_created']


# ---------- OrganizationPlatformLedger ----------
class PlatformFeeLineInline(admin.TabularInline):
    model = PlatformFeeLine
    extra = 0
    readonly_fields = ['order', 'order_amount', 'fee_amount', 'created_at']
    can_delete = False
    show_change_link = True


@admin.register(OrganizationPlatformLedger)
class OrganizationPlatformLedgerAdmin(admin.ModelAdmin):
    list_display = [
        'organization',
        'cycle_start',
        'cycle_due',
        'accumulated_sales',
        'accumulated_fee',
        'status',
        'days_until_due_display',
        'updated_at',
    ]
    list_filter = ['status', 'cycle_due', 'organization']
    search_fields = ['organization__name', 'organization__full_name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [PlatformFeeLineInline]
    date_hierarchy = 'cycle_due'
    ordering = ['-cycle_start']

    @admin.display(description='Days until due')
    def days_until_due_display(self, obj):
        days = obj.days_until_due
        if obj.status == obj.STATUS_PAID:
            return '—'
        if days < 0:
            return f'Overdue by {abs(days)} day(s)'
        return f'{days} day(s)'


# ---------- PlatformFeeLine ----------
@admin.register(PlatformFeeLine)
class PlatformFeeLineAdmin(admin.ModelAdmin):
    list_display = [
        'ledger',
        'order',
        'order_amount',
        'fee_amount',
        'created_at',
    ]
    list_filter = ['created_at', 'ledger__organization']
    search_fields = [
        'ledger__organization__name',
        'order__id',
    ]
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


# ---------- PlatformFeeRemittance ----------
@admin.register(PlatformFeeRemittance)
class PlatformFeeRemittanceAdmin(admin.ModelAdmin):
    list_display = [
        'receipt_no',
        'ledger',
        'amount_paid',
        'payment_date',
        'due_date',
        'management_rep_name',
        'recorded_by',
        'created_at',
    ]
    list_filter = ['payment_date', 'due_date']
    search_fields = [
        'receipt_no',
        'management_rep_name',
        'ledger__organization__name',
        'ledger__organization__full_name',
        'notes',
    ]
    readonly_fields = ['receipt_no', 'created_at']
    date_hierarchy = 'payment_date'
    ordering = ['-payment_date']


# ---------- simple registrations ----------
admin.site.register(User)
admin.site.register(Category)
admin.site.register(ProductVariant)