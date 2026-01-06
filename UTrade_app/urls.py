from django.urls import path
from .views import items_views

urlpatterns = [
     path('', items_views.landing_page, name='landingpage'),
]