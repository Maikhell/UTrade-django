from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q
from ..models import CartItem, Order, OrderItem, Review, User, Product, Services, SystemLog,PreOrderRequest,Category, CategoryAttribute
from ..utils import log_action
from itertools import chain
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.http import HttpResponse
from django.utils import timezone
from django.contrib import messages 
import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test, login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.http import JsonResponse
from ..models import ProhibitedWord, Category, MeetupLocation

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
        
        users = users.order_by(sort_param)

        approved_products = Product.objects.filter(status='Approved')
        approved_services = Services.objects.filter(status='Approved')

        if search_query:
            approved_products = approved_products.filter(
                Q(name__icontains=search_query) | 
                Q(seller__first_name__icontains=search_query) |
                Q(seller__last_name__icontains=search_query) |
                Q(variants__price__icontains=search_query) # Products use variants
            ).distinct()

            approved_services = approved_services.filter(
                Q(name__icontains=search_query) |
                Q(seller__first_name__icontains=search_query) |
                Q(seller__last_name__icontains=search_query) |
                Q(base_price__icontains=search_query)          
            ).distinct()

        if pre_order_filter:
            is_pre = pre_order_filter == 'True'
            approved_products = approved_products.filter(pre_order=is_pre)

        for p in approved_products: p.is_service = False
        for s in approved_services: s.is_service = True
        
        approved_items = sorted(
            chain(approved_products, approved_services),
            key=lambda instance: instance.id, reverse=True
        )

        pending_products = Product.objects.filter(status='Pending')
        pending_services = Services.objects.filter(status='Pending')
        
        incoming_preorders = PreOrderRequest.objects.filter(
            seller__user_role='management'
        ).select_related('buyer', 'product_variant__product').order_by('-created_at')
        
        all_orders = Order.objects.all().distinct()

        context = {
            'org_name': "UTrade Global Management",
            'users': users,
            'verified_count': User.objects.filter(status='verified').count(),
            
            # Inventory / Live Listings
            'approved_items': approved_items,
            'approved_count': len(approved_items), 
            'active_products_count': approved_products.count(), 
            'active_services_count': approved_services.count(), 
            
            # Pending Items
            'pending_products': pending_products,
            'pending_products_count': pending_products.count(),
            'pending_services': pending_services,
            'pending_services_count': pending_services.count(),
            
            # Logs and Orders
            'logs': SystemLog.objects.all()[:50],
            'incoming_orders': incoming_preorders,
            'completed_orders': all_orders.filter(status='Completed'),
        }

        return render(request, 'UTrade_app/management/management.html', context)
    


def update_status(request, type, id):
    new_status = request.GET.get('status')
    
    if type == 'service':
        item = get_object_or_404(Services, id=id)
    elif type == 'product':
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

def service_details(request, service_id):
    service = get_object_or_404(Services, id=service_id)
    context = {
        'service': service,
    }
    return render(request, 'UTrade_app/management/service_detail.html', context)
def product_details(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'UTrade_app/management/product_detail_view.html', {'product': product})

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
    elif report_type == 'all_services':
        title = "All Services Report"
        data = Services.objects.all()
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
    return render(request, 'UTrade_app/management/management_security.html', context)

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