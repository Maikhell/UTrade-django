from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()
class UserProfile(models.Model):
    user = models.OneToOneField( settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='Profile')
    user_image = models.ImageField(upload_to='user_images/', blank=True, null= True)
    user_number = models.IntegerField(verbose_name='Contact')
    
class Products(models.Model):
    product_name = models.CharField(max_length=255, verbose_name='Name')
    product_description = models.TextField(blank=True, null=True, verbose_name='Description')
    product_price = models.DecimalField(max_digits= 10, decimal_places=2)
    product_quantity = models.IntegerField(verbose_name= 'Quantity')
    product_rating = models.DecimalField(max_digits = 3, decimal_places=2, verbose_name='Rating')
    product_image = models.ImageField(upload_to= 'products_images/', blank= True ,null= True, verbose_name='Image')
    


