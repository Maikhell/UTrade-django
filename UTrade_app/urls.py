from django.urls import path
from .views import (
    items_views, user_views, authenticate,
    admin_views, cart_views, order_views, chat_views,
    organization_views, management_views, alumni_views,
    otplink_views
)

urlpatterns = [

    # =========================================================================
    # Authentication & Basic User Access
    # =========================================================================
    path('', items_views.ProductListView.as_view(), name='landingpage'),
    path('register/', user_views.UserCreateView.as_view(), name='user.register'),
    path('login/', authenticate.Login.as_view(), name='user.login'),
    path('logout/', authenticate.Logout.as_view(), name='user.logout'),
    path('account/', user_views.UserAccountView.as_view(), name='user.account'),
    path('userprofile/', user_views.UserProfileView.as_view(), name='user.profile'),
    path('update-terms-agreement/', user_views.update_terms_agreement, name='update_terms_agreement'),
    path('profile/update-cor/', user_views.update_cor, name='update_cor'),
    path('profile/register-officer/', user_views.register_officer, name='register_officer'),
    path('seller/reports/sales/', user_views.seller_sales_report, name='seller.sales_report'),
    path('verify-email/', otplink_views.verify_otp, name='verify_otp'),

    # =========================================================================
    # Marketplace: Products & Services
    # =========================================================================
    path('browse/', items_views.ProductListView.as_view(), name='product.list'),
    path('addproduct/', items_views.ProductCreateView.as_view(), name='product.create'),
    path('product/<int:pk>/', items_views.ProductDetailView.as_view(), name='product.detail'),
    path('product/<int:pk>/delete/', user_views.ProductDeleteView.as_view(), name='product.delete'),
    path('product/<int:product_id>/variant/create/', user_views.variant_create, name='variant.create'),
    path('variant/<int:pk>/delete/', management_views.variant_delete, name='variant.delete'),
    path('wishlist/', items_views.WishlistListView.as_view(), name='wishlist.list'),
    path('wishlist/toggle/<int:product_id>/', items_views.toggle_wishlist, name='toggle_wishlist'),
    path('shop/<int:seller_id>/', items_views.StorefrontView.as_view(), name='storefront'),
    path('api/get-attributes/<int:category_id>/', items_views.get_attributes, name='get_attributes'),
    path('api/prohibited-words/', items_views.prohibited_words_api, name='prohibited_words_api'),
    path('api/staged-product/add/', items_views.add_to_staging_ajax, name='add_to_staging_ajax'),
    path('api/staged-product/<int:staged_id>/', items_views.get_staged_product_details, name='get_staged_details'),
    path('api/staged-product/delete/<int:staged_id>/', items_views.delete_staged_product, name='delete_staged'),
    path('api/next-product-code/', items_views.delete_staged_product, name='api.next_product_code'),

    # =========================================================================
    # Shopping Cart & Checkout
    # =========================================================================
    path('cart/', cart_views.cart_detail, name='cart_detail'),
    path('cart/add/<int:variant_id>/', cart_views.add_to_cart, name='add_to_cart'),
    path('cart/add-batch/', items_views.BatchAddToCartView.as_view(), name='cart.add_batch'),
    path('cart/update/<int:item_id>/', cart_views.update_cart, name='update_cart'),
    path('cart/remove/<int:item_id>/', cart_views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', cart_views.checkout_view, name='checkout_view'),
    path('checkout/place-order/', order_views.place_order, name='place_order'),

    # =========================================================================
    # Orders & Reviews
    # =========================================================================
    path('orders/', order_views.order_history, name='order_history'),
    path('order/success/<int:order_id>/', order_views.order_success, name='order_success'),
    path('order/accept/<int:order_id>/', order_views.accept_order, name='order.accept'),
    path('order/delivered/<int:order_id>/', order_views.mark_order_delivered, name='order.delivered'),
    path('order/confirm-receipt/<int:order_id>/', order_views.confirm_receipt, name='confirm_receipt'),
    path('order/<int:order_id>/rate/', order_views.submit_review, name='submit_rating'),
    path('order/receipt/<int:order_id>/', order_views.generate_receipt, name='generate_receipt'),
    path('orders/cancel/<int:order_id>/', order_views.cancel_order, name='cancel_order'),

    # =========================================================================
    # Pre-Orders (Seller + Buyer)
    # =========================================================================
    path('preorder/request/<int:variant_id>/', order_views.submit_preorder_request, name='preorder.request'),
    path('preorder/request-batch/', items_views.BatchPreOrderView.as_view(), name='preorder.request_batch'),
    path('preorder/update-status/<int:order_id>/', order_views.update_preorder_status, name='update_preorder_status'),
    path('preorder/receipt/<int:preorder_id>/', order_views.generate_preorder_receipt, name='generate_preorder_receipt'),
    path('seller/preorder/<int:preorder_id>/ready/', user_views.preorder_mark_ready, name='preorder.mark_ready'),
    path('seller/preorder/<int:preorder_id>/complete/', user_views.preorder_mark_completed, name='preorder.mark_completed'),
    path('seller/reports/preorders/', user_views.seller_preorder_report, name='seller.preorder_report'),

    # =========================================================================
    # Communication (Chats)
    # =========================================================================
    path('inbox/', chat_views.inbox, name='inbox'),
    path('chat/<int:conversation_id>/', chat_views.chat_view, name='chat_view'),
    path('start_chat/<int:product_id>/', chat_views.start_chat, name='start_chat'),
    path('chat/upload/', chat_views.upload_chat_attachment, name='chat_upload'),
    path('chat/report/<int:conversation_id>/', chat_views.report_conversation, name='chat.report'),

    # =========================================================================
    # Admin (Campus Administration)
    # =========================================================================
    path('admindashboard/', admin_views.AdminDashboard.as_view(), name='admin.dashboard'),
    path('pendingproducts/', admin_views.AdminReviewListView.as_view(), name='admin.review'),
    path('generate-pdf/', admin_views.generate_pdf, name='generate.pdf'),
    path('admin-dashboard/create-account/', admin_views.admin_create_account, name='admin.create_account'),
    path('review/update/<str:item_type>/<int:item_id>/', admin_views.UpdateStatusView.as_view(), name='update_status'),

    # =========================================================================
    # Organization Management
    # =========================================================================
    path('organization/dashboard/', organization_views.organization_panel, name='organization.panel'),
    path('organization/update/<str:item_type>/<int:item_id>/', organization_views.update_status_org, name='org.update_status'),
    path('organization/generate-pdf/', organization_views.generate_pdf_orgs, name='generate.pdf.orgs'),

    # =========================================================================
    # Alumni Dashboard & Reports
    # =========================================================================
    path('alumni-association/', alumni_views.alumni_dashboard_view, name='alumni.dashboard'),
    path('alumni-association/alumni/<int:user_id>/', alumni_views.update_alumni_status, name='alumni.update.status'),
    path('alumni-association/generate-pdf/', alumni_views.generate_alumni_report, name='generate.reports.pdf'),

    # =========================================================================
    # Management – Dashboard & Core
    # =========================================================================
    path('management/panel/', management_views.ManagementPanelView.as_view(), name='management.panel'),
    path('management/dashboard/', user_views.UserProductsView.as_view(), name='dashboard'),
    path('management/update/<str:type>/<int:id>/', management_views.update_status, name='management.update'),
    path('productview/<int:product_id>/', management_views.product_details, name='product.detail.view'),
    path('management/generate-report/', management_views.generate_report_pdf, name='generate.report.pdf'),
    path('management/active-listings/', management_views.active_listings, name='active_listings'),
    path('management/cbrgu-products/', management_views.cbrgu_products, name='cbrgu_products'),

    # =========================================================================
    # Management – Orders & Pre-Orders
    # =========================================================================
    path('management/orders/', management_views.management_orders, name='management_orders'),
    path('management/orders/batch/', management_views.management_orders_batch, name='management_orders_batch'),
    path('management/preorders/', management_views.management_preorders, name='management_preorders'),
    path('management/preorders/batch/', management_views.management_preorders_batch, name='management_preorders_batch'),

    # =========================================================================
    # Management – Remittance
    # =========================================================================
    path('management/remittance/', management_views.remittance_management, name='remittance_management'),
    path('management/remittance/notify/<int:ledger_id>/', management_views.notify_org_remittance, name='notify_org_remittance'),
    path('management/remittance/record/', management_views.record_platform_remittance, name='record_platform_remittance'),
    path('management/remittance/receipt/<int:remittance_id>/', management_views.platform_fee_receipt, name='platform_fee_receipt'),
    path('remittance/logs/', management_views.remittance_logs_view, name='remittance_logs'),
    path('remittance/receipt/<int:ledger_id>/', management_views.view_remittance_receipt, name='view_remittance_receipt'),

    # =========================================================================
    # Management – Logs & Reports
    # =========================================================================
    path('management/logs-reports/', management_views.logs_reports, name='logs_reports'),
    path('management/logs-reports/generate/', management_views.generate_logs_report, name='generate_logs_report'),
    path('management/logs-reports/action/<int:report_id>/', management_views.report_action, name='report_action'),

    # =========================================================================
    # Management – Settings (split security pages)
    # =========================================================================
    # Page views
    path('management/settings/prohibited-words/', management_views.add_prohibited_words, name='add_prohibited_words'),
    path('management/settings/categories/', management_views.add_categories, name='add_categories'),
    path('management/settings/pickup-spots/', management_views.add_pickup_spots, name='add_pickup_spots'),

    # Legacy entry (redirects to prohibited-words)
    path('management/security/', management_views.security_admin, name='security_admin'),
    path('management/security/api/prohibited-words/', management_views.get_prohibited_words, name='api_prohibited_words'),

    # AJAX – Add
    path('management/security/bad-words/add/', management_views.add_bad_word, name='add_bad_word'),
    path('management/security/categories/add/', management_views.add_category, name='add_category'),
    path('management/security/meetups/add/', management_views.add_meetup, name='add_meetup'),

    # AJAX – Delete (paths match management.js)
    path('management/security/delete-word/<int:word_id>/', management_views.delete_bad_word, name='delete_bad_word'),
    path('management/security/categories/delete/<int:cat_id>/', management_views.delete_category, name='delete_category'),
    path('management/security/delete-meetup/<int:loc_id>/', management_views.delete_meetup, name='delete_meetup'),

    # Product moderation
    path('management/product/<int:product_id>/reject/', management_views.management_reject_product, name='management.product_reject'),
    path('management/product/<int:product_id>/unlist/', management_views.management_unlist_product, name='management.product_unlist'),
    path('management/suspend-user/', chat_views.management_suspend_user, name='management.suspend_user'),
    
    path('management/admin/add-accounts/', management_views.add_accounts, name='add_accounts'),
    path('management/admin/all-users/', management_views.all_users, name='all_users'),
    path('management/product/<int:product_id>/unlist-form/', management_views.management_unlist_product_form, name='management.product_unlist_form'),
    path('management/product/<int:product_id>/list/', management_views.management_list_product, name='management.product_list'),
    path('product/<int:pk>/edit/', management_views.ProductUpdateView.as_view(), name='product.edit'),
]