from django.db import models
from .base import BaseItem      # Import the parent class
from .user_models import User   

class ServiceCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Category')
    def __str__(self):
        return self.name
    
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