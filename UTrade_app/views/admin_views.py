import json
import uuid
from datetime import datetime
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Count, Q
from django.template.loader import get_template

from xhtml2pdf import pisa

from ..models import Product, Services, User, ProhibitedWord
User = get_user_model()
class AdminDashboard(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'UTrade_app/admin/admin_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        search_query = self.request.GET.get('search', '')
        status_filter = self.request.GET.get('status_filter', '')
        role_filter = self.request.GET.get('role_filter', '')
        sort_by = self.request.GET.get('sort', '-date_joined')

        users = User.objects.exclude(id=self.request.user.id)

        if search_query:
            users = users.filter(
                Q(username__icontains=search_query) | 
                Q(email__icontains=search_query)
            )

        if status_filter:
            users = users.filter(status=status_filter)

        if role_filter:
            if role_filter == 'admin':
                users = users.filter(is_staff=True)
            elif role_filter == 'officer':
                users = users.filter(is_officer=True)
            else:
                users = users.filter(user_role=role_filter)

        users = users.order_by(sort_by)

        user_stats = User.objects.aggregate(
            total_users=Count('id'),
            total_admin=Count('id', filter=Q(is_staff=True) | Q(user_role='management') | Q(user_role='alumni')),
            verified_count=Count('id', filter=Q(status='verified', is_staff=False, is_officer=False)),
            unverified_count=Count('id', filter=Q(status='unverified'))
        )
        
        context.update({
            'users': users, 
            'total_user_count': user_stats['total_users'],
            'admin_count': user_stats['total_admin'],        
            'verified_count': user_stats['verified_count'],
            'unverified': user_stats['unverified_count'],
            'pending_officers': User.objects.filter(officer_status__iexact='Pending'),
        })
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        target_user = get_object_or_404(User, id=user_id)

        if action == 'UpdateUser':
            new_status = request.POST.get('status')
            new_role = request.POST.get('user_role') 
            
            target_user.status = new_status
            target_user.user_role = new_role
            
            target_user.is_staff = False
            target_user.is_superuser = False
            target_user.is_officer = False
            
            if new_role == 'officer':
                target_user.is_officer = True
                target_user.organization = request.POST.get('organization') or ''
                target_user.position = request.POST.get('position') or ''
                target_user.officer_status = 'verified'
            
            elif new_role == 'alumni_assoc':
                target_user.organization = 'Alumni Association'
                target_user.position = 'Member'
                target_user.officer_status = '' 
                
            elif new_role == 'student':
                target_user.organization = ''
                target_user.position = ''
                target_user.officer_status = '' 
                               
            elif new_role == 'management':
                target_user.organization = 'Management'
                target_user.position = 'Member'
                target_user.officer_status = '' 
                
            elif new_role == 'campus_admin':
                target_user.organization = 'Campus Admin'
                target_user.position = 'Member'
                target_user.officer_status = '' 
                
            else: 
                target_user.organization = ''
                target_user.position = ''
                target_user.officer_status = '' 
            
            target_user.save()
            messages.success(request, f"Permissions for {target_user.username} updated to {new_role}.")

        elif action == 'ApproveOfficer': 
            target_user.officer_status = 'verified'
            target_user.is_officer = True
            target_user.user_role = 'officer' 
            target_user.save()
            messages.success(request, f"Officer privileges granted to {target_user.username}.")
        
        elif action == 'RejectOfficer':   
            target_user.officer_status = 'Rejected'
            target_user.is_officer = False
            target_user.organization = ''
            target_user.position = ''
            target_user.save()
            messages.warning(request, f"Officer application for {target_user.username} rejected.")
            
        return redirect('admin.dashboard')
@staff_member_required
def update_item_status(request, item_id): 
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        item_type = data.get('item_type') 
        
        ModelClass = Product if item_type == 'product' else Services
        
        item = get_object_or_404(ModelClass, id=item_id)
        
        item.status = new_status
        
        if hasattr(item, 'is_authorized'):
            item.is_authorized = (new_status == 'Approved')
            
        item.save()
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        print(f"DEBUG ERROR: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

class AdminReviewListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'UTrade_app/admin/product_review_list.html'

    def get_queryset(self):
        return Product.objects.filter(status='Pending')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['pending_products'] = Product.objects.filter(status='Pending').select_related('seller', 'category').order_by('created_at')
        context['pending_services'] = Services.objects.filter(status='Pending').select_related('seller', 'category').order_by('created_at')
        context['pending_users'] = User.objects.filter(status__iexact='Pending').order_by('date_joined')
        context['pending_officers'] = User.objects.filter(officer_status__iexact='Pending')
        
        special_roles = ['management', 'campus_admin', 'org_officer', 'alumni_assoc']
        context['pending_roles'] = User.objects.filter(
            role__in=special_roles, 
            status='Pending'
        ).order_by('date_joined')   
        return context

    def test_func(self):
        return self.request.user.is_staff

logger = logging.getLogger(__name__)

class UpdateStatusView(View):
    def post(self, request, item_type, item_id):
        try:
            data = json.loads(request.body)
            new_status = data.get('status', '').lower().strip()
            item_type = item_type.lower().strip()

            if item_type == 'officer' and request.user.is_staff:
                target_user = get_object_or_404(User, id=item_id)
            if new_status == 'approved':
                target_user.officer_status = 'verified'
                target_user.is_officer = True  
            else:
                target_user.officer_status = 'Rejected'
                target_user.save()
            return JsonResponse({'status': 'success'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        

    
def generate_pdf(request):
    user_filter = request.GET.get('filter', 'all')
    
    users = User.objects.all()

    if user_filter == 'admin':
        users = users.filter(user_role='campus_admin')
        report_title = "Campus Administrators Report"
        
    elif user_filter == 'management':
        users = users.filter(user_role='management')
        report_title = "University Management Report"
        
    elif user_filter == 'officer':
        users = users.filter(is_officer=True)
        report_title = "Student Officers Directory"
        
    elif user_filter == 'alumni':
        users = users.filter(user_role='alumni')
        report_title = "Alumni Association Report"
        
    elif user_filter == 'verified':
        users = users.filter(status='verified', is_staff=False, is_officer=False)
        report_title = "Verified Students Report"
        
    elif user_filter == 'unverified':
        users = users.filter(status='unverified', is_staff=False)
        report_title = "Unverified Students Report"
        
    else:
        users = users.all()
        report_title = "Full User Directory Report"
        
    users = users.order_by('-date_joined')

    context = {
        'users': users,
        'report_title': report_title,
        'generated_by': request.user.username,
        'current_date': datetime.now(), 
    }

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{user_filter}_report_{datetime.now().strftime("%Y%m%d")}.pdf"'
    
    template = get_template('UTrade_app/admin/pdf_template.html')
    html = template.render(context)

    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
       return HttpResponse('Error generating PDF')
       
    return response


User = get_user_model()

def admin_create_account(request):
    if not request.user.is_staff:
        return redirect('home')

    if request.method == 'POST':
        role = request.POST.get('special_role') 
        uname = request.POST.get('username')
        pword = request.POST.get('password')
        full_name = request.POST.get('full_name', '')

        if User.objects.filter(username=uname).exists():
            messages.error(request, "Username already taken.")
        else:
            unique_suffix = str(uuid.uuid4())[:8]
            
            new_user = User.objects.create_user(
                username=uname, 
                password=pword,
                email=f"{uname}_{unique_suffix}@utrade.system",
                student_no=f"ADM-{unique_suffix}"
            )
            
            new_user.first_name = full_name
            new_user.user_role = role
            
            new_user.is_verified = True 
            
            if role == 'alumni_assoc':
                new_user.organization = 'Alumni Association'

            new_user.save()
            
            messages.success(request, f"Success! {role.replace('_', ' ').title()} account created.")
            return redirect('admin.dashboard')

    return render(request, 'UTrade_app/admin/admin_create_account.html')