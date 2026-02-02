from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator

class User(AbstractUser):
    student_no = models.CharField(max_length=20, unique=True, validators=[RegexValidator(r'^\d+$', message = "Studen number must be numeric")]
    )
    USERNAME_FIELD = 'student_no'
    REQUIRED_FIELDS = ['username', 'email']
    username = models.CharField(max_length=150,blank=True, unique=True, null=True)
    display_name = models.CharField(max_length = 150, blank= True, unique = True, null = True)
    email = models.EmailField(blank=True, null=True)
    image = models.ImageField(upload_to='images/', blank=True, null= True)
    number = models.IntegerField(blank=True, null=True, verbose_name='contact')
    status = models.CharField( null=True, blank=True,default='unverified')
    def __str__(self):
       return str(self.username) if self.username else str(self.student_no)

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Category')
    def __str__(self):
        return self.name
    
class Products(models.Model):
    name = models.CharField(max_length=255, verbose_name='name')
    description = models.TextField(blank=True, null=True, verbose_name='description')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="category")
    price = models.DecimalField(max_digits= 10, decimal_places=2)
    stocks = models.IntegerField(verbose_name= 'stocks')
    rating = models.DecimalField(max_digits = 3, decimal_places=2,  null=True, blank= True, default= 0.0, verbose_name='rating')
    image = models.ImageField(upload_to= 'images/', blank= True ,null= True, verbose_name='image')
    sold = models.IntegerField(verbose_name= 'sold', default= 0)
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=120, verbose_name='status', choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.product_name
    
class ProductImage(models.Model):
    product = models.ForeignKey(Products, related_name='images', on_delete=models.CASCADE)
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
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    quantity = models.PositiveBigIntegerField(default=1)
    def get_cost(self):
        return self.product.price * self.quantity