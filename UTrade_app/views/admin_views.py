import json
from django.views.generic import ListView,TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from ..models import Product


User = get_user_model()
class AdminDashboard(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'UTrade_app/admin/admin_dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context ['users'] = User.objects.all().order_by('-date_joined')
        context['admin'] = User.objects.filter(is_staff=True).count
        context ['unverified'] = User.objects.filter(status = 'unverified')
        context ['verified'] = User.objects.filter(status = 'verified')
        context ['products'] = Product.objects.all().order_by('-created_at')
        context ['pending_products'] = Product.objects.filter(status ='Pending').order_by('created_at')
        return context
    
@staff_member_required
def update_product_status(request, product_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            product = Product.objects.get(id=product_id)
            product.status = new_status
            if new_status == 'Approved':
                product.is_authorized = True
            else:
                product.is_authorized = False
                
            product.save()
            return JsonResponse({'status': 'success'})
        except Product.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Product not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

class AdminReviewListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Product
    template_name = 'UTrade_app/admin/product_review_list.html'
    context_object_name = 'pending_items'
    
    def get_queryset(self):
        return Product.objects.filter(status ='Pending').order_by('created_at')
    def test_func(self):
        return self.request.user.is_staff

