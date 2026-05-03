from django.db import models
from .base import BaseItem, MeetupLocation
from django.db.models import Avg, Sum 
from .user_models import User
from .orders_models import Order, OrderItem
from .organization_models import Organization

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.name

class Product(BaseItem):
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="products")
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_listings')
    sold = models.IntegerField(default=0)
    pre_order = models.BooleanField(default=False)
    
    OWNER_TYPE_CHOICES = [
        ('PERSONAL', 'Personal'),
        ('ORGANIZATION', 'Organization'),
        ('MANAGEMENT', 'Management'),
    ]
    owner_type = models.CharField(
        max_length=15, 
        choices=OWNER_TYPE_CHOICES, 
        default='PERSONAL'
    )

    related_org = models.ForeignKey(
        Organization, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="products",
        help_text="Select the organization if this is not a personal listing"
    )

    meetup_location = models.ForeignKey(
        MeetupLocation, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="products"    
    )

    PAYMENT_METHODS = [
        ('GCASH', 'GCash Only'),
        ('COP', 'Cash on Pickup Only'),
        ('BOTH', 'GCash and COP'),
    ]
    accepted_payments = models.CharField(
        max_length=10, 
        choices=PAYMENT_METHODS, 
        default='BOTH'
    )

    def __str__(self):
        return self.name
    
    @property
    def get_total_stock(self):
        total = self.variants.aggregate(Sum('stocks'))['stocks__sum']
        return total if total is not None else 0

    @property
    def get_price_range(self):
        variants = self.variants.all()
        if not variants: return "0.00"
        prices = [v.price for v in variants]
        return f"{min(prices)} - {max(prices)}" if min(prices) != max(prices) else f"{min(prices)}"

    @property
    def owner_name(self):
        return self.seller.get_full_name() or self.seller.username

    @property
    def display_seller_name(self):
        if self.owner_type == 'ORGANIZATION' and self.related_org:
            return self.related_org.full_name
        return self.owner_name

    def average_rating(self):
        avg = self.reviews.aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else 0.0
class StagedProduct(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='staged_products')
    
    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    pre_order = models.BooleanField(default=False)
    
    owner_type = models.CharField(max_length=15, choices=Product.OWNER_TYPE_CHOICES, default='PERSONAL')
    related_org = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True)
    
    meetup_locations_list = models.TextField(help_text="Comma-separated list of locations")
    
    accepted_payments = models.CharField(max_length=10, choices=Product.PAYMENT_METHODS, default='BOTH')
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_submitted = models.BooleanField(default=False) 

    def __str__(self):
        return f"Staged: {self.name} by {self.seller.username}"

class StagedVariant(models.Model):
    staged_product = models.ForeignKey(StagedProduct, on_delete=models.CASCADE, related_name='variants')
    variant_name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stocks = models.PositiveIntegerField(default=1)
    condition = models.CharField(max_length=50, default="Brand New")
    flaws = models.TextField(blank=True, null=True)
    image_index = models.IntegerField(null=True, blank=True) 

class StagedImage(models.Model):
    staged_product = models.ForeignKey(StagedProduct, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/staged/')
    is_main = models.BooleanField(default=False)
class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        
    def __str__(self):
        return f"{self.user.username} - {self.product.name}"    
    
class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='images/')
    variant = models.ForeignKey(
        'ProductVariant', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='variant_images'
    )

    def __str__(self):
        return f"Image for {self.product.name}"
class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='order_reviews', null=True) 
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)]) 
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user', 'order') 

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.rating}★)"
      
class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True )
    created_at = models.DateTimeField(auto_now_add=True)
    
    @property
    def total_price(self):
        return sum(item.get_cost() for item in self.items.all())
    @property
    def count(self):
        return sum(item.quantity for item in self.items.all())
class ProductVariant(models.Model):
    product = models.ForeignKey(Product, related_name='variants', on_delete=models.CASCADE)
    variant_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stocks = models.IntegerField(default=0)
    condition = models.CharField(max_length=50, default='Brand New') 
    flaws_description = models.TextField(blank=True, null=True)
    
    assigned_image = models.ForeignKey(
        'ProductImage', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_variants'
    )

    def __str__(self):
        return f"{self.product.name} - {self.variant_name}"
    
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)    
    quantity = models.PositiveBigIntegerField(default=1)

    def get_cost(self):
        return self.variant.price * self.quantity

    def __str__(self):
        return f"{self.variant.product.name} - {self.variant.variant_name} (x{self.quantity})"
    
    def get_total_price(self):
        return self.variant.price * self.quantity
    
    @property
    def display_name(self):
        return f"{self.variant.product.name} ({self.variant.variant_name})"
class PreOrderRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('PREPARING', 'Seller Preparing Item'), 
        ('READY', 'Ready for Pickup'),          
        ('DECLINED', 'Declined'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='preorder_requests')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_preorders')
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='preorders')
    
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    full_name_at_time = models.CharField(max_length=255)
    student_no_at_time = models.CharField(max_length=50)
    course_at_time = models.CharField(max_length=100)
    section_at_time = models.CharField(max_length=50)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Pre-order: {self.product_variant.product.name} by {self.buyer.username} ({self.status})"
    def get_total_price(self):
        return self.product_variant.price * self.quantity

    def get_total_price(self):
        return self.product_variant.price * self.quantity