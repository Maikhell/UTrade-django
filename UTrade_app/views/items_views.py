from django.shortcuts import render
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic import  CreateView, ListView, DetailView
from ..forms import ProductForm
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import Product, Category, ProductImage, Wishlist 
from django.http import JsonResponse

def landing_page(request):
    return render(request, 'UTrade_app/landingpage.html')

class ProductCreateView(LoginRequiredMixin, CreateView):
    form_class = ProductForm
    template_name = 'Utrade_app/products/actions/addproduct.html'
    success_url = reverse_lazy('product.list')
    #retrieve data to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context
    
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        total_products = int(request.POST.get('total_products', 0))
        if total_products == 0:
            return super().post(request, *args, **kwargs)
        # Handle multiple products
        for i in range(total_products):
            data = {
                'name': request.POST.get(f'prod_{i}_name'),
                'price': request.POST.get(f'prod_{i}_price'),
                'stocks': request.POST.get(f'prod_{i}_stocks'),
                'description': request.POST.get(f'prod_{i}_desc'),
                'category': request.POST.get(f'prod_{i}_category'),
            }
            form = ProductForm(data, request.FILES)
            
            if form.is_valid():
                product = form.save(commit=False)
                product.seller = request.user
                product.status = 'Pending'
                # Handle the first image
                image_file = request.FILES.get(f'prod_{i}_image_0')
                if image_file:
                    product.image = image_file
                product.save()
                # Handle additional images
                image_count = int(request.POST.get(f'prod_{i}_image_count', 0))
                for j in range(1, image_count): #0 is the main image
                    extra_img = request.FILES.get(f'prod_{i}_image_{j}')
                    if extra_img:
                        ProductImage.objects.create(product=product, image=extra_img)
            else:
                return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

        return JsonResponse({'status': 'success'})
    
class ProductDetailView(DetailView):
    model = Product
    template_name = 'Utrade_app/products/actions/product_details.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related_products'] = Product.objects.filter(
            category=self.object.category,
            status='Approved'
        ).exclude(id=self.object.id)[:4]
        return context
    
class ProductListView(ListView):
    model = Product
    template_name = 'UTrade_app/marketplace.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        # Get only approved products
        queryset = Product.objects.filter(status='Approved').select_related('category') 
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.search(search_query) #searches name and description 
        #Filter by category
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['current_category'] = self.request.GET.get('category')
        if self.request.user.is_authenticated:
            user_wishlist = Wishlist.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            context['user_wishlist_ids'] = set(user_wishlist) # Sets have O(1) lookup time
        else:
            context['user_wishlist_ids'] = []
        return context
    
class WishlistListView(LoginRequiredMixin, ListView):
    model = Wishlist
    template_name = 'Utrade_app/products/actions/wishlist.html'
    context_object_name = 'wishlists'
    
    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).select_related('product').order_by('-added_at')

@login_required
def toggle_wishlist(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
        
        if not created:
            wishlist_item.delete()
            status = 'removed'
        else:
            status = 'added'
            
        return JsonResponse({'status':'success', 'action': status})
    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Product not found'})
