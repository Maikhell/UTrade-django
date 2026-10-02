from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q
from ..forms import ProductForm
from ..models import CartItem, Order, OrderItem, Review, User, Product,SystemLog,PreOrderRequest,Category, CategoryAttribute, Product, Conversation, ProductVariant, ChatMessage, SystemLog, UserReport
from ..utils import log_action
from itertools import chain
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.http import HttpResponse
from django.utils import timezone
from django.contrib import messages 
import json
from django.views.generic import UpdateView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test, login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.http import JsonResponse
from ..models import ProhibitedWord, Category, MeetupLocation
from django.core.paginator import Paginator
from django.db.models import Sum, F, Count
from django.db.models.functions import TruncDate
from datetime import timedelta
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class ManagementPanelView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        search_query = request.GET.get('search', '')
        status_filter = request.GET.get('status_filter', '')
        pre_order_filter = request.GET.get('pre_order', '')
        sort_param = request.GET.get('sort', '-date_joined')

        users = User.objects.all().exclude(id=request.user.id)

        if search_query:
            users = users.filter(
                Q(username__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(student_no__icontains=search_query)
            )

        if status_filter:
            users = users.filter(status=status_filter)
        
        users = users.order_by(sort_param)[:50] # Limit initial load for performance

        # Optimized Approved Products & Services
        approved_products = (
            Product.objects
            .filter(status='Approved')
            .select_related('seller', 'category')
            .prefetch_related('variants', 'images')
            .order_by('-created_at')
        )
        page_number = request.GET.get('page', 1)
        paginator = Paginator(approved_products, 15)
        page_obj = paginator.get_page(page_number)
        
        # Lightened User Reports (Removed heavy message prefetching for the dashboard list)
        reported_items = (
            UserReport.objects
            .select_related(
                'reporter',
                'reported_user',
                'conversation',
                'conversation__product',
                'conversation__buyer',
                'conversation__seller',
            )
            .order_by('-created_at')[:50] # Reduced limit to save RAM
        )
        
        if search_query:
            approved_products = approved_products.filter(
                Q(name__icontains=search_query) | 
                Q(seller__first_name__icontains=search_query) |
                Q(seller__last_name__icontains=search_query) |
                Q(variants__price__icontains=search_query)
            ).distinct()

        if pre_order_filter:
            is_pre = pre_order_filter == 'True'
            approved_products = approved_products.filter(pre_order=is_pre)

        # Cache counts to prevent extra database hits
        active_products_count = approved_products.count()
    

        pending_products = Product.objects.filter(status='Pending')[:50]
      
        incoming_preorders = PreOrderRequest.objects.filter(
            seller__user_role='management'
        ).select_related('buyer', 'product_variant__product').order_by('-created_at')[:50]
        
        completed_orders = Order.objects.filter(status='Completed')[:50]

        context = {
            'org_name': "UTrade Global Management",
            'users': users,
            'verified_count': User.objects.filter(status='verified').count(),
            
            # Inventory / Live Listings (Consider paginating approved_items in templates)
            'approved_count': active_products_count,
            'active_products_count': active_products_count, 
          
            
            # Pending Items
            'pending_products': pending_products,
            'pending_products_count': pending_products.count(),
            
            # Fixed: Re-using the variable instead of running the query a second time!
            'reported_items': reported_items,
            
            # Logs and Orders (Capped with slices to protect memory)
            'logs': SystemLog.objects.all()[:30],
            'incoming_orders': incoming_preorders,
            'completed_orders': completed_orders,
            
            'approved_items': page_obj,          # template already uses approved_items
            'approved_count': paginator.count,
            'active_products_count': paginator.count,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
        }

        return render(request, 'UTrade_app/management/dashboard.html', context)

class ProductUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'UTrade_app/products/edit_product.html'

    def test_func(self):
        return self.get_object().seller_id == self.request.user.id

    def form_valid(self, form):
        product = form.save(commit=False)
        product.status = 'Pending'  # force re-review after edit
        product.save()

        # Optional: update variants from POST JSON
        variants_raw = self.request.POST.get('variants')
        if variants_raw:
            import json
            try:
                variants = json.loads(variants_raw)
            except json.JSONDecodeError:
                variants = []
            for v in variants:
                vid = v.get('id')
                if vid:
                    ProductVariant.objects.filter(
                        id=vid, product=product
                    ).update(
                        variant_name=v.get('name', ''),
                        attribute_value=v.get('attribute', ''),
                        price=v.get('price') or 0,
                        stocks=v.get('stock') or 0,
                        condition=v.get('condition', 'Brand New'),
                        flaws_description=v.get('flaws', ''),
                    )
                else:
                    ProductVariant.objects.create(
                        product=product,
                        variant_name=v.get('name', ''),
                        attribute_value=v.get('attribute', ''),
                        price=v.get('price') or 0,
                        stocks=v.get('stock') or 0,
                        condition=v.get('condition', 'Brand New'),
                        flaws_description=v.get('flaws', ''),
                    )

        messages.warning(
            self.request,
            f'“{product.name}” was updated and sent back to Management for approval. '
            f'It is hidden from the marketplace until approved again.'
        )
        return redirect('seller_inventory')
def update_status(request, type, id):
    new_status = request.GET.get('status')
    
    
    if type == 'product':
        item = get_object_or_404(Product, id=id)
    elif type == 'user':
        item = get_object_or_404(User, id=id)
    
    item.status = new_status
    item.save()

    item_name = getattr(item, 'name', str(item))
    log_action(
        user=request.user,
        action=f"Status Changed to {new_status}",
        item_type=type.capitalize(),
        item_name=item_name,
        details=f"Admin updated {type} ID:{id} status to {new_status}"
    )

    messages.success(request, f"{type.capitalize()} updated successfully!")
    return redirect('management.panel')


def product_details(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related('seller', 'category')
        .prefetch_related('variants', 'images'),
        id=product_id
    )

    # ---------------------------------------
    # MEETUP AVAILABILITY
    # ---------------------------------------

    # Location
    meetup_location = (product.meetup_location_text or '').strip()

    # Available days
    raw_days = (product.available_days or '').strip()

    available_days_list = []

    if raw_days:
        available_days_list = [
            day.strip()
            for day in raw_days.split(',')
            if day.strip()
        ]

    # Time
    meetup_time_from = product.preferred_meetup_time_from
    meetup_time_to = product.preferred_meetup_time_to

    return render(
        request,
        'UTrade_app/management/product_view.html',
        {
            'product': product,

            # Meetup information
            'meetup_location': meetup_location,
            'available_days_list': available_days_list,
            'meetup_time_from': meetup_time_from,
            'meetup_time_to': meetup_time_to,
        }
    )


def generate_report_pdf(request):
    report_type = request.GET.get('report_type')
    today = timezone.now()
    
    # 1. Data Selection Logic
    data = []
    title = ""
    
    if report_type == 'live_products':
        title = "Live Inventory Report (On-Hand)"
        data = Product.objects.filter(status='Approved', pre_order=False)
    elif report_type == 'pre_orders':
        title = "Management Pre-Order Report"
        data = Product.objects.filter(status='Approved', pre_order=True)
    elif report_type == 'all_products':
        title = "Complete Product Masterlist"
        data = Product.objects.all()
    elif report_type == 'user_logs':
        title = "System Activity Logs"
        data = SystemLog.objects.all()[:100]
    elif report_type == 'completed_preorders':
        title = "Completed Pre-Order Transactions"
        data = Order.objects.filter(
            status='Completed', 
            product__pre_order=True
        ).order_by('-updated_at')
    template_path = 'UTrade_app/management/report_pdf.html'
    context = {
        'title': title,
        'data': data,
        'report_type': report_type,
        'today': today,
        'generated_by': request.user.get_full_name() or request.user.username
    }
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_{today.strftime("%Y%m%d")}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(
    html, 
    dest=response,
    encoding='utf-8' 
)
    
    if pisa_status.err:
       return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response

def is_management(user):
    return user.is_authenticated and user.user_role == 'management'

@login_required
@user_passes_test(is_management)
def security_admin(request):
    context = {
        'prohibited_words': ProhibitedWord.objects.all().order_by('-created_at'),
        'categories': Category.objects.all().order_by('name'),
        'meetups': MeetupLocation.objects.all().order_by('name'),  
    }
    # Move the template to a management folder if preferred
    return render(request, 'UTrade_app/management/security.html', context)

@require_POST
@user_passes_test(is_management)
def add_bad_word(request):
    word_text = request.POST.get('word', '').strip().lower()
    if word_text:
        word_obj, created = ProhibitedWord.objects.get_or_create(word=word_text)
        if created:
            return JsonResponse({'status': 'success', 'word': word_obj.word, 'id': word_obj.id})
        return JsonResponse({'status': 'error', 'message': 'Word already exists.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid input.'})

@require_POST
@user_passes_test(is_management)
def delete_bad_word(request, word_id):
    ProhibitedWord.objects.filter(id=word_id).delete()
    return JsonResponse({'status': 'success'})

@require_POST
@user_passes_test(is_management)
def add_category(request):
    if request.method == 'POST':
        try:
            # Parse the JSON data from the request body
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            attributes = data.get('attributes', []) # This is our list of {type, value}

            if not name:
                return JsonResponse({'status': 'error', 'message': 'Name cannot be empty.'})

            # 1. Create the Category
            category, created = Category.objects.get_or_create(name=name)
            
            if not created:
                return JsonResponse({'status': 'error', 'message': 'Category already exists.'})

            # 2. Loop through and create the linked Attributes
            for attr in attributes:
                attr_value = attr.get('value', '').strip()
                attr_type = attr.get('type', 'size')
                
                if attr_value:
                    CategoryAttribute.objects.get_or_create(
                        category=category,
                        value=attr_value,
                        attribute_type=attr_type,
                        defaults={
                            'is_custom': False, # Mark as official admin attribute
                            'created_by': request.user
                        }
                    )

            return JsonResponse({
                'status': 'success', 
                'name': category.name, 
                'id': category.id
            })

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid data format.'})
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

@require_POST
@user_passes_test(is_management)
def delete_category(request, cat_id):
    Category.objects.filter(id=cat_id).delete()
    return JsonResponse({'status': 'success'})

@require_POST
@user_passes_test(is_management)
def add_meetup(request):
    location_name = request.POST.get('location', '').strip() 
    if location_name:
        if MeetupLocation.objects.filter(name__iexact=location_name).exists():
            return JsonResponse({'status': 'error', 'message': 'Location already exists.'}, status=400)
        location = MeetupLocation.objects.create(name=location_name, added_by=request.user)
        return JsonResponse({'status': 'success', 'location': location.name, 'id': location.id})
    return JsonResponse({'status': 'error', 'message': 'Location name is required.'}, status=400)

@require_POST
@user_passes_test(is_management)
def delete_meetup(request, loc_id):
    MeetupLocation.objects.filter(id=loc_id).delete()
    return JsonResponse({'status': 'success'})

def get_prohibited_words(request):
    words = list(ProhibitedWord.objects.values_list('word', flat=True))
    return JsonResponse({'prohibited_words': words})

def is_management(user):
    return user.is_authenticated and user.user_role == 'management'


def _notify_seller(admin_user, product, message_text):
    """Open/reuse conversation as admin (buyer side) with seller, about this product."""
    conversation, _ = Conversation.objects.get_or_create(
        product=product,
        buyer=admin_user,   # management acts as initiator
        seller=product.seller,
    )
    ChatMessage.objects.create(
        conversation=conversation,
        user=admin_user,
        content=message_text,
        is_read=False,
    )
    return conversation


@login_required
@user_passes_test(is_management)
@require_POST
def management_reject_product(request, product_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

    reason = (data.get('reason') or '').strip()
    if not reason:
        return JsonResponse({'success': False, 'message': 'Reason required'}, status=400)

    product = get_object_or_404(Product, id=product_id)
    product.status = 'Rejected'
    product.save(update_fields=['status'])

    msg = (
        f"🚨 SYSTEM (Management): Your product \"{product.name}\" was rejected.\n"
        f"Reason: {reason}\n"
        f"You may edit and resubmit it for review."
    )
    _notify_seller(request.user, product, msg)

    log_action(
        user=request.user,
        action="Product Rejected",
        item_type="Product",
        item_name=product.name,
        details=f"Rejected ID:{product.id}. Reason: {reason}",
    )

    return JsonResponse({'success': True, 'message': 'Product rejected and seller notified.'})


@login_required
@user_passes_test(is_management)
@require_POST
def management_unlist_product(request, product_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

    reason = (data.get('reason') or '').strip()
    if not reason:
        return JsonResponse({'success': False, 'message': 'Reason required'}, status=400)

    product = get_object_or_404(Product, id=product_id, status='Approved')
    product.status = 'Unlisted'  # or 'Rejected' / 'Pending' — match your STATUS choices
    product.save(update_fields=['status'])

    msg = (
        f"🚨 SYSTEM (Management): Your product \"{product.name}\" was unlisted from the marketplace.\n"
        f"Reason: {reason}\n"
        f"Contact management if you have questions."
    )
    _notify_seller(request.user, product, msg)

    log_action(
        user=request.user,
        action="Product Unlisted",
        item_type="Product",
        item_name=product.name,
        details=f"Unlisted ID:{product.id}. Reason: {reason}",
    )

    return JsonResponse({'success': True, 'message': 'Product unlisted and seller notified.'})

def seller_sales_chart_data(request):
    """JSON for Chart.js — completed orders only."""
    user = request.user
    days = int(request.GET.get('days', 30))
    since = timezone.now() - timedelta(days=days)

    # Prefer OrderItem path if multi-seller cart
    qs = (
        OrderItem.objects.filter(
            product_variant__product__seller=user,
            order__status__iexact='Completed',
            order__updated_at__gte=since,  # or created_at / completed_at
        )
        .annotate(day=TruncDate('order__updated_at'))
        .values('day')
        .annotate(
            revenue=Sum(F('price') * F('quantity')),
            units=Sum('quantity'),
            orders=Count('order_id', distinct=True),
        )
        .order_by('day')
    )

    labels = [r['day'].strftime('%b %d') for r in qs if r['day']]
    revenue = [float(r['revenue'] or 0) for r in qs]
    units = [int(r['units'] or 0) for r in qs]

    return JsonResponse({
        'labels': labels,
        'revenue': revenue,
        'units': units,
    })
    
@login_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    name = product.name
    product.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': f'{name} removed.'})
    messages.success(request, f'“{name}” was removed.')
    return redirect('seller_inventory')

@login_required
@require_POST
def variant_delete(request, pk):
    variant = get_object_or_404(
        ProductVariant,
        pk=pk,
        product__seller=request.user,
    )
    product = variant.product
    variant.delete()
    # Optional: force re-review if product was live
    if product.status == 'Approved':
        product.status = 'Pending'
        product.save(update_fields=['status'])
        notice = 'Variant removed. Product returned to Pending for re-approval.'
    else:
        notice = 'Variant removed.'

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': notice})
    messages.success(request, notice)
    return redirect('seller_inventory')