from django.urls import path
from .views import items_views, services_views, user_views, authenticate, admin_views, cart_views

urlpatterns = [
     path('', items_views.landing_page, name='landingpage'),
     path('register/', user_views.UserCreateView.as_view(), name = 'user.register'),
     path('login/', authenticate.Login.as_view(), name = 'user.login'),
     path('logout/', authenticate.Logout.as_view(), name = 'user.logout'),
     path('account/', user_views.UserAccountView.as_view(), name = 'user.account'),
     path('userprofile/', user_views.UserProfileView.as_view(), name = 'user.profile'),
     
     #Admin
     path('admindashboard/', admin_views.AdminDashboard.as_view(), name="admin.dashboard"),
     path('pendingproducts/', admin_views.AdminReviewListView.as_view(), name = 'admin.review'),
     #Admin Update
     path('product-review/update/<int:product_id>/', admin_views.update_product_status, name='update_status'),
     
     #Products
     path('browse/', items_views.ProductListView.as_view(), name = 'product.list'),
     path('addproduct/', items_views.ProductCreateView.as_view(), name = 'product.create'),
     path('product/<int:pk>/', items_views.ProductDetailView.as_view(), name='product.detail'),
     path('wishlist', items_views.WishlistListView.as_view(), name = 'wishlist.list'),
     path('wishlist/toggle/<int:product_id>/', items_views.toggle_wishlist, name='toggle_wishlist'),
     path('products/', user_views.UserProductsView.as_view(), name = 'userproduct.list'),
     
     #Cart
     path('cart/', cart_views.cart_detail, name='cart_detail'),
     path('cart/add/<int:product_id>/', cart_views.add_to_cart, name= 'add_to_cart'),
     path('cart/update/<int:item_id>/', cart_views.update_cart, name='update_cart'),
     path('cart/remove/<int:item_id>/', cart_views.remove_from_cart, name='remove_from_cart'),
     #Services
     path('addservices/', services_views.ServiceCreateView.as_view(), name = 'services.create'),
     path('services/', services_views.ServiceListView.as_view(), name = 'services.list'),
]