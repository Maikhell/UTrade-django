from django.db import models
from django.db.models import Q

class SearchQuerySet(models.QuerySet):
    def search(self, query=None):
        if query is None or query.strip() == "":
            return self.all()
        return self.filter(Q(name__icontains=query) | Q(description__icontains=query)).distinct()

class BaseItem(models.Model):
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