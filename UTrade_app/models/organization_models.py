from django.db import models

class Organization(models.Model):
    name = models.CharField(max_length=50, unique=True) #"ITS"
    full_name = models.CharField(max_length=150)        #"Information Technology Society"
    course_code = models.CharField(max_length=20)       #"BSIT"
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='org_logos/', blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.course_code})"