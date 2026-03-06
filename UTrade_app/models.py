from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db.models import Q
from django.templatetags.static import static

def user_profile_path(instance, filename):
    return f'profiles/student_{instance.student_no}/{filename}'

class SearchQuerySet(models.QuerySet):
    #updated to prevent crash from non-text fields
    def search(self, query=None):
        if query is None or query.strip() == "":
            return self.all()
        return self.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query)
        ).distinct()
    
class User(AbstractUser):
    student_no = models.CharField(
        max_length=20, 
        unique=True, 
        validators=[RegexValidator(r'^\d+$', "Student number must be numeric")]
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    status = models.CharField(max_length=20, default='unverified')
    USERNAME_FIELD = 'student_no'
    REQUIRED_FIELDS = ['username', 'email']
    display_name = models.CharField(max_length=150, blank=True, null=True, unique=True)
    image = models.ImageField(
        upload_to=user_profile_path, 
        blank=True, 
        null=True, 
        verbose_name='Profile Picture'
    )
    @property
    def profile_pic_url(self):
        try:
            if self.image and self.image.url:
                return self.image.url
        except ValueError:
            pass
        return static('UTrade_app/img/default-user.png')
    @property
    def get_short_name(self):
        return self.display_name if self.display_name else self.username
    
    def __str__(self):
        return self.get_short_name

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Category')
    def __str__(self):
        return self.name

class ServiceCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Category')
    def __str__(self):
        return self.name
    
class BaseItem(models.Model):
    """Abstract model to share common fields between Products and Services"""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=10, 
        choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')],
        default='Pending'
    )

    objects = SearchQuerySet.as_manager()

    class Meta:
        abstract = True  
         
class Services(BaseItem):
    category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True)
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name="service_listings") 
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    turnaround_time = models.CharField(max_length=100, help_text="e.g. 3-5 days")

    def __str__(self):
        return f"{self.name} by {self.seller.get_short_name}"
    
class ServicesImage(models.Model):
    service = models.ForeignKey(Services, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='images/')
    
class Product(BaseItem):
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="products")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stocks = models.IntegerField(default=0)
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_listings')
    sold = models.IntegerField(default=0)

    def __str__(self):
        return self.name
    
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
    
    
class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True )
    created_at = models.DateTimeField(auto_now_add=True)
    
    @property
    def total_price(self):
        return sum(item.get_cost() for item in self.items.all())
    @property
    def count(self):
        return sum(item.quantity for item in self.items.all())
    
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveBigIntegerField(default=1)
    def get_cost(self):
        return self.product.price * self.quantity
    def get_total_price(self):
        return self.product.price * self.quantity