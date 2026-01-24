from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator

class User(AbstractUser):
    student_no = models.CharField(max_length=20, unique=True, validators=[RegexValidator(r'^\d+$', message = "Studen number must be numeric")]
    )
    USERNAME_FIELD = 'student_no'
    REQUIRED_FIELDS = ['username', 'email']
    username = models.CharField(max_length=150,blank=True, unique=True, null=True)
    email = models.EmailField(blank=True, null=True)
    user_image = models.ImageField(upload_to='user_images/', blank=True, null= True)
    user_number = models.IntegerField(blank=True, null=True, verbose_name='Contact')
    def __str__(self):
       return str(self.username) if self.username else str(self.student_no)

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Category')
    def __str__(self):
        return self.name
    
class Products(models.Model):
    product_name = models.CharField(max_length=255, verbose_name='Name')
    product_description = models.TextField(blank=True, null=True, verbose_name='Description')
    product_category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="Category")
    product_price = models.DecimalField(max_digits= 10, decimal_places=2)
    product_quantity = models.IntegerField(verbose_name= 'Quantity')
    product_rating = models.DecimalField(max_digits = 3, decimal_places=2, verbose_name='Rating')
    product_image = models.ImageField(upload_to= 'products_images/', blank= True ,null= True, verbose_name='Image')
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]
    product_status = models.CharField(max_length=120, verbose_name='Status', choices=STATUS_CHOICES, default='Pending')
    
    def __str__(self):
        return self.product_name
