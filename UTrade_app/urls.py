from django.urls import path
from .views import items_views, services_views, user_views, authenticate, admin_views, cart_views, order_views

urlpatterns = [
     path('', items_views.landing_page, name='landingpage'),
     path('register/', user_views.UserCreateView.as_view(), name = 'user.register'),
     path('login/', authenticate.Login.as_view(), name = 'user.login'),
     path('logout/', authenticate.Logout.as_view(), name = 'user.logout'),
     path('account/', user_views.UserAccountView.as_view(), name = 'user.account'),
     path('userprofile/', user_views.UserProfileView.as_view(), name = 'user.profile'),
     
     #Admin
     path('admindashboard/', admin_views.AdminDashboard.as_view(), name="admin.dashboard"),
     path('pendingproducts/', admin_views.AdminReviewListView.as_view(), name='admin.review'),
     #Admin Update
     path('review/update/<str:item_type>/<int:item_id>/', admin_views.UpdateStatusView.as_view(), name='update_status'),     
     path('browse/', items_views.ProductListView.as_view(), name = 'product.list'),
     path('addproduct/', items_views.ProductCreateView.as_view(), name = 'product.create'),
     path('product/<int:pk>/', items_views.ProductDetailView.as_view(), name='product.detail'),
     path('wishlist', items_views.WishlistListView.as_view(), name = 'wishlist.list'),
     path('wishlist/toggle/<int:product_id>/', items_views.toggle_wishlist, name='toggle_wishlist'),
     path('inventory/', user_views.UserProductsView.as_view(), name='seller_inventory'),
     path('product/<int:pk>/edit/', user_views.ProductUpdateView.as_view(), name='product.edit'),
     path('product/<int:pk>/delete/', user_views.ProductDeleteView.as_view(), name='product.delete'),
     
     #Cart
     path('cart/', cart_views.cart_detail, name='cart_detail'),
     path('cart/add/<int:variant_id>/', cart_views.add_to_cart, name='add_to_cart'),
     path('cart/update/<int:item_id>/', cart_views.update_cart, name='update_cart'),
     path('cart/remove/<int:item_id>/', cart_views.remove_from_cart, name='remove_from_cart'),
      path('checkout/', cart_views.checkout_view, name='checkout_view'),
      
     #Checkout & Order 
     path('checkout/place-order/', order_views.place_order, name='place_order'), 
     path('order/success/<int:order_id>/', order_views.order_success, name='order_success'),    
      
     #Services
     path('addservices/', services_views.ServiceCreateView.as_view(), name = 'services.create'),
     path('services/', services_views.ServiceListView.as_view(), name = 'services.list'),
     
     #Users
     path('verify-account/', user_views.submit_verification, name='user.verify'),
]