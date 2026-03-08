from django.shortcuts import render
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic import  CreateView, ListView, DetailView
from ..forms import ProductForm
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import Product, Category, ProductImage, Wishlist, CartItem 
from django.http import JsonResponse

def landing_page(request):
    return render(request, 'UTrade_app/landingpage.html')

class ProductCreateView(LoginRequiredMixin, CreateView):
    form_class = ProductForm
    template_name = 'Utrade_app/products/actions/addproduct.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context
    
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        total_products = int(request.POST.get('total_products', 0))
        
        # If it's a standard single-form submission
        if total_products == 0:
            return super().post(request, *args, **kwargs)

        # Handle multiple products via loop
        try:
            for i in range(total_products):
                raw_category = request.POST.get(f'prod_{i}_category')
                
                if raw_category and raw_category.startswith('NEW:'):
                    new_name = raw_category.replace('NEW:', '').strip()
                    
                    #Search for an existing category regardless of Case (Upper/Lower)
                    category_obj = Category.objects.filter(name__iexact=new_name).first()
                    
                    if not category_obj:
                        # If it doesn't exist, create it in Title Case
                        # .title() makes "SNAckS" -> "Snacks"
                        category_obj = Category.objects.create(name=new_name.title())
                    
                    category_id = category_obj.id
                else:
                    category_id = raw_category
                # Using form validation even for bulk items
                data = {
                    'name': request.POST.get(f'prod_{i}_name'),
                    'price': request.POST.get(f'prod_{i}_price'),
                    'stocks': request.POST.get(f'prod_{i}_stocks'),
                    'description': request.POST.get(f'prod_{i}_desc'),
                    'category': category_id,
                    'meetup_spot': request.POST.get(f'prod_{i}_meetup'),
                    'payment_method': request.POST.get(f'prod_{i}_payment'),
                }
                # Create a temporary form instance to validate this specific product
                form = ProductForm(data, {'image': request.FILES.get(f'prod_{i}_image_0')})
                
                if form.is_valid():
                    product = form.save(commit=False)
                    product.seller = request.user
                    product.status = 'Pending'
                    product.save()

                    # Handle Additional Gallery Images
                    image_count = int(request.POST.get(f'prod_{i}_image_count', 0))
                    # Bulk create gallery images to save DB hits
                    gallery_imgs = [
                        ProductImage(product=product, image=request.FILES.get(f'prod_{i}_image_{j}'))
                        for j in range(1, image_count)
                        if request.FILES.get(f'prod_{i}_image_{j}')
                    ]
                    ProductImage.objects.bulk_create(gallery_imgs)
                else:
                    # Rolling back happens automatically due to @transaction.atomic
                    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
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
        # ... keep your existing get_queryset logic the same ...
        queryset = Product.objects.filter(status='Approved').select_related('category') 
        # (etc...)
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['current_category'] = self.request.GET.get('category')
        
        if self.request.user.is_authenticated:
            user_wishlist = Wishlist.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            context['user_wishlist_ids'] = set(user_wishlist)
            
            user_cart = CartItem.objects.filter(cart__user=self.request.user).values_list('product_id', flat=True)
            context['user_cart_ids'] = set(user_cart)
        else:
            context['user_wishlist_ids'] = []
            context['user_cart_ids'] = [] 
            
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

