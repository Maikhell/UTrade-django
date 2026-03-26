from django.db import models
from .base import BaseItem
from django.db.models import Avg, Sum 
from .user_models import User

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.name

class Product(BaseItem):
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="products")
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_listings')
    sold = models.IntegerField(default=0)

    def __str__(self):
        return self.name
    
    @property
    def get_total_stock(self):
        """Calculates the sum of stocks from all variants associated with this product."""
        total = self.variants.aggregate(Sum('stocks'))['stocks__sum']
        return total if total is not None else 0

    @property
    def get_price_range(self):
        variants = self.variants.all()
        if not variants: return "0.00"
        prices = [v.price for v in variants]
        return f"{min(prices)} - {max(prices)}" if min(prices) != max(prices) else f"{min(prices)}"

    def average_rating(self):
        avg = self.reviews.aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else 0.0
    
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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)]) 
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user') 

    def __str__(self):
        return f"{self.rating} stars - {self.product.name}"  
      
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

    @property
    def display_name(self):
        return f"{self.variant.product.name} ({self.variant.variant_name})"