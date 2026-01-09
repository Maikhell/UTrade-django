from django.shortcuts import render
from django.views.generic import View, CreateView
from ..forms import ProductForm

def landing_page(request):
    return render(request, 'UTrade_app/landingpage.html')

class ProductCreateView(CreateView):
    form_class = ProductForm
    template_name = 'Utrade_app/listproduct.html'