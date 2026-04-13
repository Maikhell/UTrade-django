from django.urls import path
from .views import items_views, services_views, user_views, authenticate, admin_views, cart_views, order_views, chat_views


urlpatterns = [
     path('', items_views.ProductListView.as_view(), name='landingpage'), 
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
     path('orders/', order_views.order_history, name='order_history'),
     path('checkout/place-order/', order_views.place_order, name='place_order'), 
     path('order/success/<int:order_id>/', order_views.order_success, name='order_success'),    
     path('order/accept/<int:order_id>/', order_views.accept_order, name='order.accept'),
     #path('order/reject/<int:order_id>/', order_views.reject_order, name='order.reject'),
     path('order/delivered/<int:order_id>/', order_views.mark_order_delivered, name='order.delivered'),
     path('order/confirm-receipt/<int:order_id>/', order_views.confirm_receipt, name='confirm_receipt'),
     path('order/delivered/<int:order_id>/', order_views.mark_order_delivered, name='order.delivered'),
     #Rating
     path('order/<int:order_id>/rate/', order_views.submit_review, name='submit_rating'),
     path('addservices/', services_views.ServiceCreateView.as_view(), name = 'services.create'),
     path('services/', services_views.ServiceListView.as_view(), name = 'services.list'),
     
     #Chats
     path('inbox/', chat_views.inbox, name='inbox'),
     path('chat/<int:conversation_id>/', chat_views.chat_view, name='chat_view'),
     path('start_chat/<int:product_id>/', chat_views.start_chat, name='start_chat'),
     
     #Users
     path('verify-account/', user_views.submit_verification, name='user.verify'),
     path('update-terms-agreement/', user_views.update_terms_agreement, name='update_terms_agreement'),
     
     path('security/admin/', admin_views.security_admin, name='security_admin'),

     path('api/prohibited-words/', admin_views.get_prohibited_words, name='api_prohibited_words'),
     path('security/bad-words/add/', admin_views.add_bad_word, name='add_bad_word'),
     path('security/categories/add/', admin_views.add_category, name='add_category'),
     path('security/meetups/add/', admin_views.add_meetup, name='add_meetup'),
     
     #Delete
     path('security/delete-word/<int:word_id>/', admin_views.delete_bad_word, name='delete_bad_word'),
     path('security/categories/delete/<int:cat_id>/', admin_views.delete_category, name='delete_category'),
     path('security/meetups/delete/<int:loc_id>/', admin_views.delete_meetup, name='delete_meetup'),
]