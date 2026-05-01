from django.urls import path
from .views import (
    items_views, services_views, user_views, authenticate, 
    admin_views, cart_views, order_views, chat_views, 
    organization_views, management_views,alumni_views
)

urlpatterns = [
    # --- Authentication & Basic User Access ---
    path('', items_views.ProductListView.as_view(), name='landingpage'), 
    path('register/', user_views.UserCreateView.as_view(), name='user.register'),
    path('login/', authenticate.Login.as_view(), name='user.login'),
    path('logout/', authenticate.Logout.as_view(), name='user.logout'),
    path('account/', user_views.UserAccountView.as_view(), name='user.account'),
    path('userprofile/', user_views.UserProfileView.as_view(), name='user.profile'),
    path('update-terms-agreement/', user_views.update_terms_agreement, name='update_terms_agreement'),
    path('profile/update-cor/', user_views.update_cor, name='update_cor'),
    path('profile/register-officer/', user_views.register_officer, name='register_officer'),

    # --- Marketplace: Products & Services ---
    path('browse/', items_views.ProductListView.as_view(), name='product.list'),
    path('addproduct/', items_views.ProductCreateView.as_view(), name='product.create'),
    path('product/<int:pk>/', items_views.ProductDetailView.as_view(), name='product.detail'),
    path('inventory/', user_views.UserProductsView.as_view(), name='seller_inventory'),
    path('product/<int:pk>/edit/', user_views.ProductUpdateView.as_view(), name='product.edit'),
    path('product/<int:pk>/delete/', user_views.ProductDeleteView.as_view(), name='product.delete'),
    path('wishlist/', items_views.WishlistListView.as_view(), name='wishlist.list'),
    path('wishlist/toggle/<int:product_id>/', items_views.toggle_wishlist, name='toggle_wishlist'),
    
    path('services/', services_views.ServiceListView.as_view(), name='services.list'),
    path('addservices/', services_views.ServiceCreateView.as_view(), name='services.create'),

    # --- Shopping Cart & Checkout ---
    path('cart/', cart_views.cart_detail, name='cart_detail'),
    path('cart/add/<int:variant_id>/', cart_views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', cart_views.update_cart, name='update_cart'),
    path('cart/remove/<int:item_id>/', cart_views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', cart_views.checkout_view, name='checkout_view'),

    # --- Orders & Reviews ---
    path('orders/', order_views.order_history, name='order_history'),
    path('checkout/place-order/', order_views.place_order, name='place_order'), 
    path('order/success/<int:order_id>/', order_views.order_success, name='order_success'),    
    path('order/accept/<int:order_id>/', order_views.accept_order, name='order.accept'),
    path('order/delivered/<int:order_id>/', order_views.mark_order_delivered, name='order.delivered'),
    path('order/confirm-receipt/<int:order_id>/', order_views.confirm_receipt, name='confirm_receipt'),
    path('order/<int:order_id>/rate/', order_views.submit_review, name='submit_rating'),
    path('preorder/request/<int:variant_id>/', order_views.submit_preorder_request, name='preorder.request'),
    path('preorder/update-status/<int:order_id>/', order_views.update_preorder_status, name='update_preorder_status'),  
    path('order/receipt/<int:order_id>/', order_views.generate_receipt, name='generate_receipt'), 
    path('preorder/receipt/<int:preorder_id>/', order_views.generate_preorder_receipt, name='generate_preorder_receipt'),
    # --- Communication (Chats) ---
    path('inbox/', chat_views.inbox, name='inbox'),
    path('chat/<int:conversation_id>/', chat_views.chat_view, name='chat_view'),
    path('start_chat/<int:product_id>/', chat_views.start_chat, name='start_chat'),

    # --- Admin (Campus Administration) ---
    path('admindashboard/', admin_views.AdminDashboard.as_view(), name="admin.dashboard"),
    path('pendingproducts/', admin_views.AdminReviewListView.as_view(), name='admin.review'),
    path('generate-pdf/', admin_views.generate_pdf, name='generate.pdf'),
    path('admin-dashboard/create-account/', admin_views.admin_create_account, name='admin.create_account'),
    path('review/update/<str:item_type>/<int:item_id>/', admin_views.UpdateStatusView.as_view(), name='update_status'),     

    # --- Organization Management ---
    path('organization/dashboard/', organization_views.organization_panel, name='organization.panel'),
    path('organization/update/<str:item_type>/<int:item_id>/', organization_views.update_status_org, name='org.update_status'),
    path('organization/generate-pdf/', organization_views.generate_pdf_orgs, name='generate.pdf.orgs'), 
    path('orders/cancel/<int:order_id>/', order_views.cancel_order, name='cancel_order'),
    
    # --- Management Dashboard & Reports ---
    path('managementn/panel/', management_views.ManagementPanelView.as_view(), name='management.panel'),
    path('management/update/<str:type>/<int:id>/', management_views.update_status, name='management.update'),
    path('service/<int:service_id>/', management_views.service_details, name='service.details'),
    path('productview/<int:product_id>/', management_views.product_details, name='product.detail.view'),
    path('management/generate-report/', management_views.generate_report_pdf, name='generate.report.pdf'),

    # --- Alumni Dashboard & Reports ---
    path('alumni-association/', alumni_views.alumni_dashboard_view, name='alumni.dashboard'),
    path('alumni-association/alumni/<int:user_id>/', alumni_views.update_alumni_status, name='alumni.update.status'),
    path('alumni-association/generate-pdf/', alumni_views.generate_alumni_report, name='generate.reports.pdf'),
    
    # --- Security & Global Settings (Management Only) ---
    path('management/security/', management_views.security_admin, name='security_admin'),
    path('management/security/api/prohibited-words/', management_views.get_prohibited_words, name='api_prohibited_words'),
    
    # Add/Create Operations
    path('management/security/bad-words/add/', management_views.add_bad_word, name='add_bad_word'),
    path('management/security/categories/add/', management_views.add_category, name='add_category'),
    path('management/security/meetups/add/', management_views.add_meetup, name='add_meetup'),
    
    # Delete Operations
    path('management/security/delete-word/<int:word_id>/', management_views.delete_bad_word, name='delete_bad_word'),
    path('management/security/categories/delete/<int:cat_id>/', management_views.delete_category, name='delete_category'),
    path('management/security/delete-meetup/<int:loc_id>/', management_views.delete_meetup, name='delete_meetup'),
    
    #
    path('api/prohibited-words/', items_views.prohibited_words_api, name='prohibited_words_api'),

    ]
   