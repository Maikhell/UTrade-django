import json
from django.views.generic import ListView,TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from ..models import Product
from django.db.models import Count, Q


User = get_user_model()
class AdminDashboard(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'UTrade_app/admin/admin_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        #Get all user statistics in ONE query
        user_stats = User.objects.aggregate(
            total_admin=Count('id', filter=Q(is_staff=True)),
            unverified=Count('id', filter=Q(status='unverified')),
            verified=Count('id', filter=Q(status='verified'))
        )
        
        # Fetching data with select_related to optimize template rendering
        all_products = Product.objects.all().select_related('seller', 'category').order_by('-created_at')
        
        context.update({
            'users': User.objects.all().order_by('-date_joined')[:10], # Limit to latest 10 for dashboard speed
            'admin_count': user_stats['total_admin'],
            'unverified_count': user_stats['unverified'],
            'verified_count': user_stats['verified'],
            'products': all_products[:10], # Only show recent products
            'pending_products': [p for p in all_products if p.status == 'Pending'][:5], # Filter in Python memory
        })
        return context
    
@staff_member_required
def update_product_status(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        
        # Atomic update: efficient way to change specific fields
        updated_count = Product.objects.filter(id=product_id).update(
            status=new_status,
            is_authorized=(new_status == 'Approved')
        )

        if updated_count == 0:
             return JsonResponse({'status': 'error', 'message': 'Product not found'}, status=404)
             
        return JsonResponse({'status': 'success'})
        
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

class AdminReviewListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Product
    template_name = 'UTrade_app/admin/product_review_list.html'
    context_object_name = 'pending_items'
    
    def get_queryset(self):
        return Product.objects.filter(status ='Pending').order_by('created_at')
    def test_func(self):
        return self.request.user.is_staff

