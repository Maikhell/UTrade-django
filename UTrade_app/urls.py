from django.urls import path
from .views import items_views, user_views, authenticate

urlpatterns = [
     path('', items_views.landing_page, name='landingpage'),
     path('register/', user_views.UserCreateView.as_view(), name = 'user.register'),
     path('login/', authenticate.user_login, name = 'user.login'),
     
     path('browse/', items_views.ProductListView.as_view(), name = 'product.show')
]