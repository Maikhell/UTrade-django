from django.urls import path
from .views import items_views, user_views, authenticate, admin_views

urlpatterns = [
     path('', items_views.landing_page, name='landingpage'),
     path('register/', user_views.UserCreateView.as_view(), name = 'user.register'),
     path('login/', authenticate.Login.as_view(), name = 'user.login'),
     path('logout/', authenticate.Logout.as_view(), name = 'user.logout'),
     path('account/', user_views.UserAccountView.as_view(), name = 'user.account'),
     
     #Admin
     path("admindashboard/", admin_views.AdminDashboard.as_view(), name="admin.dashboard"),
     
     #Products
     path('browse/', items_views.ProductListView.as_view(), name = 'product.list'),
     path('addproduct/', items_views.ProductCreateView.as_view(), name = 'product.create'),
     
]