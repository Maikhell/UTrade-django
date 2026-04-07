import json
import logging
from django.views.generic import ListView,TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from ..models import Product, Services, User
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404

User = get_user_model()
class AdminDashboard(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'UTrade_app/admin/admin_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user_stats = User.objects.aggregate(
            total_admin=Count('id', filter=Q(is_staff=True)),
            unverified=Count('id', filter=Q(status='unverified')),
            verified=Count('id', filter=Q(status='verified'))
        )
        
        all_products = Product.objects.all().select_related('seller', 'category').prefetch_related('variants').order_by('-created_at')
        
        context.update({
            'users': User.objects.all().order_by('-date_joined')[:10],
            'admin': user_stats['total_admin'],        
            'unverified': user_stats['unverified'],   
            'verified': user_stats['verified'],      
            'products': all_products[:10],
            'pending_products': [p for p in all_products if p.status == 'Pending'][:5],
        })
        return context
    
@staff_member_required
def update_item_status(request, item_id): # Renamed for clarity
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        item_type = data.get('item_type') 
        
        ModelClass = Product if item_type == 'product' else Services
        
        # Use get_object_or_404 for cleaner error handling
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
        
        # Fetch Pending Products
        context['pending_products'] = Product.objects.filter(status='Pending')\
            .select_related('seller', 'category')\
            .prefetch_related('variants', 'images')\
            .order_by('created_at')
            
        # Fetch Pending Services
        context['pending_services'] = Services.objects.filter(status='Pending')\
            .select_related('seller', 'category')\
            .prefetch_related('images')\
            .order_by('created_at')
        #Retrieve the pending users dapat
        context['pending_users'] = User.objects.filter(status='Pending').only(
            'first_name', 'last_name', 'course', 'section', 'student_no', 'cor_file'
        ).order_by('date_joined')
        return context

    def test_func(self):
        return self.request.user.is_staff

logger = logging.getLogger(__name__)

class UpdateStatusView(View):
    def post(self, request, item_type, item_id):
        try:
            data = json.loads(request.body)
            new_status = data.get('status')

            item_type = item_type.lower().strip()

            if item_type == 'user':
                target_user = get_object_or_404(User, id=item_id)
                if new_status == 'Approved':
                    target_user.status = 'verified'
                    target_user.is_active = True
                else:
                    target_user.status = 'Rejected'
                target_user.save()
                return JsonResponse({'status': 'success'})

            elif item_type == 'product':
                target_product = get_object_or_404(Product, id=item_id)
                target_product.status = new_status
                target_product.save()
                return JsonResponse({'status': 'success'})

            elif item_type == 'service':
                target_service = get_object_or_404(Services, id=item_id)
                target_service.status = new_status
                target_service.save()
                return JsonResponse({'status': 'success'})

            return JsonResponse({'status': 'error', 'message': 'Invalid item type'}, status=400)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)