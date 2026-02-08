from django.shortcuts import render,redirect
from django.urls import reverse_lazy
from django.views.generic import  CreateView, ListView
from ..forms import ProductForm
from ..models import Products, Category, ProductImage 
from django.http import JsonResponse
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
    def post(self, request, *args, **kwargs):
        total_products = int(request.POST.get('total_products', 0))
        
        if total_products == 0:
            return super().post(request, *args, **kwargs)

        for i in range(total_products):
            category_id = request.POST.get(f'prod_{i}_category')
            category = Category.objects.get(id=category_id)
            
            product = Products.objects.create(
                name=request.POST.get(f'prod_{i}_name'),
                price=request.POST.get(f'prod_{i}_price'),
                stocks=request.POST.get(f'prod_{i}_stocks'),
                description=request.POST.get(f'prod_{i}_desc'),
                category=category,
                seller=request.user,
                status='Pending'
            )
            image_count = int(request.POST.get(f'prod_{i}_image_count', 0))
            for j in range(image_count):
                image_file = request.FILES.get(f'prod_{i}_image_{j}')
                
                if j == 0:
                    product.image = image_file
                    product.save()
                else:
                    ProductImage.objects.create(product=product, image=image_file)

        return JsonResponse({'status': 'success'})
    
class ProductListView(ListView):
    model = Products
    template_name = 'UTrade_app/marketplace.html'
    context_object_name = 'products'

    def get_queryset(self):
        queryset = Products.objects.filter(status='Approved').order_by('-created_at')        
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['current_category'] = self.request.GET.get('category')
        return context
    
class SellerProductsView(ListView):
    model = Products
    template_name = 'UTrade_app/seller_inventory.html'
    context_object_name = 'my_products'

    def get_queryset(self):
        return Products.objects.filter(seller=self.request.user).order_by('-created_at')