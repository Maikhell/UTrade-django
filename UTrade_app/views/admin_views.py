import json
from django.views.generic import ListView,TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from ..models import Product, Services
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
        
        # Some fields might only exist on Product (like is_authorized)
        # We use getattr/setattr to be safe
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
            
        return context

    def test_func(self):
        return self.request.user.is_staff
