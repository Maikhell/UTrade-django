from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from django.http import HttpResponseForbidden
from ..models import User, SystemLog

from django.template.loader import get_template
from xhtml2pdf import pisa
from django.http import HttpResponse
import io

@login_required
def alumni_dashboard_view(request):
    current_role = str(request.user.user_role).strip()
    if current_role != 'alumni_assoc' and not request.user.is_staff:
        return HttpResponseForbidden(f"Access Denied: Role '{current_role}' unauthorized.")
    
    search_query = request.GET.get('search', '')
    
    pending_users = User.objects.filter(
        user_role='alumni', 
        status='unverified' 
    ).order_by('-date_joined')

    all_alumni_list = User.objects.filter(
        user_role='alumni', 
        status='verified'
    )
    
    if search_query:
        all_alumni_list = all_alumni_list.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(student_no__icontains=search_query) |
            Q(course__icontains=search_query)
        )
        
    alumni_logs = SystemLog.objects.filter(
        Q(item_type='Alumni') | Q(action__icontains='Verified')
    ).order_by('-timestamp')[:50]

    context = {
        'pending_users': pending_users,
        'all_alumni_list': all_alumni_list,
        'alumni_logs': alumni_logs,
        'total_alumni_count': User.objects.filter(user_role='alumni', status='verified').count(),
        'pending_alumni_count': pending_users.count(),
        'verified_recent_count': User.objects.filter(user_role='alumni', status='verified').count(), 
    }

    return render(request, 'UTrade_app/alumniassoc/alumni_dashboard.html', context)

@login_required
def update_alumni_status(request, user_id):
    # Match the role check logic from above
    current_role = str(request.user.user_role).strip()
    if current_role != 'alumni_assoc' and not request.user.is_staff:
        return HttpResponseForbidden()

    target_user = get_object_or_404(User, id=user_id)
    new_status = request.GET.get('status') 

    if new_status == 'verified':
        # Updating the correct field 'status'
        target_user.status = 'verified'
        target_user.save()
        
        SystemLog.objects.create(
            user=request.user,
            action="Verified Alumni ID",
            item_name=target_user.get_full_name(),
            item_type="Alumni"
        )
        messages.success(request, f"Account for {target_user.get_full_name()} has been successfully verified.")
    
    elif new_status == 'unverified':
        target_user.status = 'unverified'
        target_user.save()
        messages.warning(request, f"Verification for {target_user.get_full_name()} was declined.")

    return redirect('alumni.dashboard')

@login_required
def generate_alumni_report(request):
    report_type = request.GET.get('report_type')
    
    # 1. Fetch Data
    if report_type == 'alumni_masterlist':
        title = "Verified Alumni Masterlist"
        queryset = User.objects.filter(user_role='alumni', status='verified').order_by('last_name')
    else:
        title = "Verification Activity Logs"
        queryset = SystemLog.objects.filter(
            Q(item_type='Alumni') | Q(action__icontains='Verified')
        ).order_by('-timestamp')

    # 2. Prepare Context
    context = {
        'queryset': queryset,
        'title': title,
        'report_type': report_type,
        'request': request
    }

    # 3. Render Template to HTML String
    template = get_template('UTrade_app/alumniassoc/alumni_report_pdf.html')
    html = template.render(context)

    # 4. Convert HTML String to PDF
    result = io.BytesIO()
    # Ensure encoding is UTF-8 to handle special characters
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)

    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{report_type}.pdf"'
        return response
    
    return HttpResponse(f"Error generating PDF: {pdf.err}", status=400)