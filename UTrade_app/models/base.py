from django.db import models
from django.db.models import Q
from .user_models import User

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
class ProhibitedWord(models.Model):
    word = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.word

    class Meta:
        verbose_name_plural = "Prohibited Words"
class MeetupLocation(models.Model):
    name = models.CharField(max_length=255, unique=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Meetup Locations"