from django.db import models

class Products(models.Model):
    product_name = models.CharField(max_length=255, verbose_name='Name')
    product_description = models.TextField(blank=True, null=True, verbose_name='Description')
    product_price = models.DecimalField(max_digits= 10, decimal_places=2)
    product_quantity = models.IntegerField(verbose_name= 'Quantity')
    product_rating = models.DecimalField(max_digits = 3, decimal_places=2, verbose_name='Rating')
    product_image = models.ImageField(upload_to= 'products_images/', blank= True ,null= True, verbose_name='Image')
    


