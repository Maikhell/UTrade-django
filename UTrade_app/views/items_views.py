from django.shortcuts import render
from django.views.generic import View, CreateView, ListView
from ..forms import ProductForm
from ..models import Products
def landing_page(request):
    return render(request, 'UTrade_app/landingpage.html')

class ProductCreateView(CreateView):
    form_class = ProductForm
    template_name = 'Utrade_app/listproduct.html'
    
    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)
    
    
class ProductListView(ListView):
    model = Products
    template_name = 'UTrade_app/homepage.html'
    
    