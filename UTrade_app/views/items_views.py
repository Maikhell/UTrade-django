from django.shortcuts import render,redirect
from django.urls import reverse_lazy
from django.views.generic import  CreateView, ListView
from ..forms import ProductForm
from ..models import Products
def landing_page(request):
    return render(request, 'UTrade_app/landingpage.html')

class ProductCreateView(CreateView):
    form_class = ProductForm
    template_name = 'Utrade_app/products/actions/addproduct.html'
    success_url = reverse_lazy ('product.list')
    
    def form_valid (self,form):
        self.object = form.save(commit=False)
        self.object.product_status = 'Pending'
        self.object.owner = self.request.user
        self.object.save()
        
        return redirect(self.success_url)
    
class ProductListView(ListView):
    model = Products
    template_name = 'UTrade_app/homepage.html'
    
    