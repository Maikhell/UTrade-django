from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
import io
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from ..models import User, Product, Order

def organization_panel(request):
    officer_org = request.user.organization 
    org_to_course = {
        'ITS': 'BSIT',
        'BSE': 'EDUC',
        'JPIA': 'BSA',
        'CBA': 'BSBA',
        'ACS': 'BSCS',
        'BSHMS': 'BSHM',
        'TES': 'BSED',
        'LCDCS': 'BSCRIM',
        'LLP': 'BSP',
        'LMS-JMA': 'BSBA-MM',
        'SHR': 'BSBA-HR',
    }

    target_course = org_to_course.get(officer_org)
    
    search_query = request.GET.get('search')
    status_filter = request.GET.get('status_filter')
    role_filter = request.GET.get('role_filter')
    sort_param = request.GET.get('sort', '-date_joined') # Default to newest

    if target_course:
        org_users = User.objects.filter(course=target_course)

        # Apply Search Logic
        if search_query:
            org_users = org_users.filter(
                Q(username__icontains=search_query) | 
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(student_no__icontains=search_query)
            )

        if status_filter:
            org_users = org_users.filter(status__iexact=status_filter)

        # Apply Role Filter
        if role_filter:
            if role_filter == 'officer':
                org_users = org_users.filter(is_officer=True)
            elif role_filter == 'student':
                org_users = org_users.filter(is_officer=False)

        # Apply Sorting (matches the 'value' in your <select> options)
        if sort_param == 'username':
            org_users = org_users.order_by('username')
        elif sort_param == '-username':
            org_users = org_users.order_by('-username')
        elif sort_param == 'date_joined':
            org_users = org_users.order_by('date_joined')
        else:
            org_users = org_users.order_by('-date_joined')
        
        # Other Queries for the Dashboard
        org_products = Product.objects.filter(seller__course=target_course).order_by('-created_at')
        pending_products = org_products.filter(status='Pending')
        pending_users = User.objects.filter(course=target_course, status__iexact='Pending')
        
        org_orders = Order.objects.filter(
            items__product_variant__product__seller__course=target_course
        ).distinct().order_by('-created_at')

        incoming_orders = org_orders.filter(status='Pending')
        completed_orders = org_orders.filter(status='Completed')
        verified_count = User.objects.filter(course=target_course, status='verified').count()

    else:
        # Fallback for users without a valid organization
        org_users = User.objects.none()
        org_products = Product.objects.none()
        pending_products = Product.objects.none()
        pending_users = User.objects.none()
        incoming_orders = Order.objects.none()
        completed_orders = Order.objects.none()
        verified_count = 0

    context = {
        'org_name': officer_org,
        'target_course': target_course,
        'users': org_users,
        'products': org_products,
        'pending_products': pending_products, 
        'pending_users': pending_users,       
        'incoming_orders': incoming_orders,
        'completed_orders': completed_orders,
        'verified_count': verified_count,
    }
    
    return render(request, 'UTrade_app/organization/organization_panel.html', context)

def update_status_org(request, item_type, item_id):
    requested_status = request.GET.get('status')    
    if item_type == 'user' and requested_status == 'approved':
        final_status = 'verified'
    else:
        final_status = requested_status
    if item_type == 'user':
        obj = get_object_or_404(User, id=item_id)
        obj.status = final_status
        obj.save()
        messages.success(request, f"Student {obj.get_full_name()} is now {final_status}.")
        
    elif item_type == 'product':
        obj = get_object_or_404(Product, id=item_id)
        obj.status = requested_status
        obj.save()
        messages.success(request, f"Product '{obj.name}' has been {requested_status}.")
        
    return redirect('organization.panel')

def generate_pdf_orgs(request):
    report_filter = request.GET.get('filter', 'all')
    officer_org = request.user.organization
    
    org_to_course = {
        'ITS': 'BSIT', 'BSE': 'EDUC', 'JPIA': 'BSA', 
        'CBA': 'BSBA', 'ACS': 'BSCS'
    }
    target_course = org_to_course.get(officer_org)

    base_filter = (
        Q(course=target_course, user_role='student') | 
        Q(organization=officer_org, is_officer=True)
    )

    users = User.objects.filter(base_filter).exclude(
        user_role__in=['management', 'campus_admin', 'alumni']
    )

    # 3. Apply the Modal Filters
    if report_filter == 'verified':
        users = users.filter(status='verified')
    elif report_filter == 'unverified':
        users = users.filter(status='unverified')
    elif report_filter == 'officer':
        users = users.filter(is_officer=True, organization=officer_org)

    # 4. Final Processing
    users = users.order_by('last_name')

    template_path = 'UTrade_app/organization/user_report_pdf.html'
    context = {
        'users': users,
        'report_type': report_filter.replace('_', ' ').title(),
        'org_name': officer_org,
        'course': target_course,
    }
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{officer_org}_Report.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)
    return response