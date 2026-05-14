from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
import io
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from ..models import User, Product, Order

def organization_panel(request):
    organization_obj = request.user.org_link 
    
    search_query = request.GET.get('search')
    status_filter = request.GET.get('status_filter')
    role_filter = request.GET.get('role_filter')
    sort_param = request.GET.get('sort', '-date_joined')

    if organization_obj:
        target_course = organization_obj.course_code
        org_users = User.objects.filter(org_link=organization_obj)

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

        if role_filter:
            if role_filter == 'officer':
                org_users = org_users.filter(is_officer=True)
            elif role_filter == 'student':
                org_users = org_users.filter(is_officer=False)

        if sort_param in ['username', '-username', 'date_joined']:
            org_users = org_users.order_by(sort_param)
        else:
            org_users = org_users.order_by('-date_joined')
        
        org_products = Product.objects.filter(
            Q(seller__org_link=organization_obj) | Q(related_org=organization_obj)
        ).distinct().order_by('-created_at')

        pending_products = org_products.filter(status='Pending')
        pending_users = User.objects.filter(
            course=target_course, 
            status__iexact='Pending'
        )
        org_orders = Order.objects.filter(
            items__product_variant__product__seller__org_link=organization_obj
        ).distinct().order_by('-created_at')

        incoming_orders = org_orders.filter(status='Pending')
        completed_orders = org_orders.filter(status='Completed')
        verified_count = org_users.filter(status='verified').count()

    else:
        target_course = "None"
        org_users = User.objects.none()
        org_products = Product.objects.none()
        pending_products = Product.objects.none()
        pending_users = User.objects.none()
        incoming_orders = Order.objects.none()
        completed_orders = Order.objects.none()
        verified_count = 0

    context = {
        'org_name': organization_obj.name if organization_obj else "No Organization",
        'org_full_name': organization_obj.full_name if organization_obj else "No Organization Assigned",
        'target_course': target_course,
        'users': org_users,
        'products': org_products,
        'pending_products': pending_products, 
        'pending_users': pending_users,       
        'incoming_orders': incoming_orders,
        'completed_orders': completed_orders,
        'verified_count': verified_count,
    }
    
    return render(request, 'UTrade_app/organization/dashboard.html', context)

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
    organization_obj = request.user.org_link
    
    if not organization_obj:
        return HttpResponse("Unauthorized", status=401)

    target_course = organization_obj.course_code

    base_filter = (
        Q(course=target_course, user_role='student') | 
        Q(org_link=organization_obj, is_officer=True)
    )

    users = User.objects.filter(base_filter).exclude(
        user_role__in=['management', 'campus_admin', 'alumni']
    )

    if report_filter == 'verified':
        users = users.filter(status='verified')
    elif report_filter == 'unverified':
        users = users.filter(status='unverified')
    elif report_filter == 'officer':
        users = users.filter(is_officer=True, org_link=organization_obj)

    users = users.order_by('last_name')

    template_path = 'UTrade_app/reports/user_report_pdf.html'
    context = {
        'users': users,
        'report_type': report_filter.replace('_', ' ').title(),
        'org_name': organization_obj.name,
        'course': target_course,
    }
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{organization_obj.name}_Report.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)
    return response