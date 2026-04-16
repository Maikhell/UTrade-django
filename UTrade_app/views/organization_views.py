from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from ..models import User, Product, Order

def organization_panel(request):
    # ... (auth checks) ...

    officer_org = request.user.organization 
    org_to_course = {
        'ITS': 'BSIT',
        'BSE': 'EDUC',
        'JPIA': 'BSA',
        'CBA': 'BSBA',
    }

    target_course = org_to_course.get(officer_org)

    if target_course:

        org_users = User.objects.filter(course=target_course).order_by('-date_joined')
        
        org_products = Product.objects.filter(seller__course=target_course).order_by('-created_at')
        
        pending_products = org_products.filter(status='Pending')
        
        pending_users = org_users.filter(status__iexact='Pending')
        
        org_orders = Order.objects.filter(
            items__product_variant__product__seller__course=target_course
        ).distinct().order_by('-created_at')

        incoming_orders = org_orders.filter(status='Pending')
        completed_orders = org_orders.filter(status='Completed')
    else:
        org_users = User.objects.none()
        org_products = Product.objects.none()
        pending_products = Product.objects.none()
        pending_users = User.objects.none()
        incoming_orders = Order.objects.none()
        completed_orders = Order.objects.none()

    context = {
        'org_name': officer_org,
        'target_course': target_course,
        'users': org_users,
        'products': org_products,
        'pending_products': pending_products, 
        'pending_users': pending_users,       
        'incoming_orders': incoming_orders,
        'completed_orders': completed_orders,
        'verified_count': org_users.filter(status='verified').count(),
    }
    
    return render(request, 'UTrade_app/organization/organization_panel.html', context)

def update_status_org(request, item_type, item_id):
    new_status = request.GET.get('status')
    
    if item_type == 'user':
        obj = get_object_or_404(User, id=item_id)
        obj.status = new_status
        obj.save()
        messages.success(request, f"Student {obj.get_full_name()} has been {new_status}.")
        
    elif item_type == 'product':
        obj = get_object_or_404(Product, id=item_id)
        obj.status = new_status
        obj.save()
        messages.success(request, f"Product '{obj.name}' has been {new_status}.")
        
    return redirect('organization.panel')