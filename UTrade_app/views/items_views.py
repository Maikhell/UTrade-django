from django.shortcuts import render,redirect
from django.urls import reverse_lazy
from django.views.generic import  CreateView, ListView
from ..forms import ProductForm
from ..models import Products, Category
def landing_page(request):
    return render(request, 'UTrade_app/landingpage.html')

class ProductCreateView(CreateView):
    form_class = ProductForm
    template_name = 'Utrade_app/products/actions/addproduct.html'
    success_url = reverse_lazy ('product.list')
    
    def get_context_data(self, **kwargs):
        context  = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        
        return context
    def form_valid (self,form):
        self.object = form.save(commit=False)
        self.object.product_status = 'Approved'
        self.object.product_rating = 0.0
        self.object.owner = self.request.user
        self.object.save()
        return super().form_valid(form)
    
class ProductListView(ListView):
    model = Products
    template_name = 'UTrade_app/homepage.html'
    context_object_name = 'products'

    def get_queryset(self):
        return Products.objects.filter(status='Pending').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context