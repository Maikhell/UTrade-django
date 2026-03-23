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
        
        # 1. User Statistics
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
def update_product_status(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

    try:
        #Parse Data
        data = json.loads(request.body)
        new_status = data.get('status')
        
        #Update Object
        product = Product.objects.get(id=product_id)
        product.status = new_status
        
        #Handle authorization logic
        if new_status == 'Approved':
            product.is_authorized = True
        else:
            product.is_authorized = False
            
        product.save()
        return JsonResponse({'status': 'success'})
        
    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Product not found'}, status=404)
    except Exception as e:
        # Log the actual error to the terminal
        print(f"DEBUG ERROR: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

class AdminReviewListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Product
    template_name = 'UTrade_app/admin/product_review_list.html'
    context_object_name = 'pending_items'
    
    def get_queryset(self):
        # Add prefetch_related('variants') here!
        return Product.objects.filter(status='Pending')\
                              .select_related('seller', 'category')\
                              .prefetch_related('variants', 'images')\
                              .order_by('created_at')

    def test_func(self):
        return self.request.user.is_staff
