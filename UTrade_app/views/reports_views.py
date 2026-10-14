from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
import io
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from ..models import User, Product, Order,OrganizationPlatformLedger
from django.utils import timezone


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