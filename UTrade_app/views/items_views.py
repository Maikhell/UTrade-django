from django.shortcuts import render
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic import  CreateView, ListView, DetailView
from ..forms import ProductForm
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import Product, Category, ProductImage, Wishlist, CartItem 
from django.http import JsonResponse
import re

def landing_page(request):
    return render(request, 'UTrade_app/landingpage.html')

class ProductCreateView(LoginRequiredMixin, CreateView):
    form_class = ProductForm
    template_name = 'Utrade_app/products/actions/addproduct.html'
    
    # List of keywords to flag.lowercase and without spaces.
    BANNED_KEYWORDS = [
        'alcohol','drugs' 'beer', 'wine', 'vodka', 'whiskey', 
        'ecigarette', 'vape', 'smoke', 'tobacco', 'cigarette',
        'examanswer', 'leakage', 'leak', 'cheating'
    ]

    def is_content_prohibited(self, text):
        """
        Advanced check for banned words, leetspeak (4lcohol, C1G), 
        and bypass characters (v.a.p.e).
        """
        if not text:
            return None
            
        # leetspeak: Map numbers/symbols to letters
        translations = {
            '4': 'a', '@': 'a', '1': 'i', '!': 'i', '3': 'e', 
            '0': 'o', '5': 's', '$': 's', '7': 't', '8': 'b'
        }
        
        # Convert to lowercase and translate characters
        text = text.lower()
        for char, replacement in translations.items():
            text = text.replace(char, replacement)
            
        # Strip all non-alphabetic characters (removes spaces, dots, dashes, etc.)
        # This turns "V.A.P.E" or "V 4 P 3" into "vape"
        clean_text = re.sub(r'[^a-z]', '', text)

        # Scan for banned keywords
        for word in self.BANNED_KEYWORDS:
            if word in clean_text:
                return word
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context
    
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        total_products = int(request.POST.get('total_products', 0))
        
        # Fallback for standard single-form submission
        if total_products == 0:
            return super().post(request, *args, **kwargs)

        try:
            for i in range(total_products):
                # Retrieve raw data from POST
                prod_name = request.POST.get(f'prod_{i}_name', '')
                prod_desc = request.POST.get(f'prod_{i}_desc', '')

                flagged_name = self.is_content_prohibited(prod_name)
                flagged_desc = self.is_content_prohibited(prod_desc)

                if flagged_name or flagged_desc:
                    word = flagged_name or flagged_desc
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Product "{prod_name}" was flagged for prohibited content ({word}). Please comply with community guidelines.'
                    }, status=400)

                raw_category = request.POST.get(f'prod_{i}_category')
                if raw_category and raw_category.startswith('NEW:'):
                    new_name = raw_category.replace('NEW:', '').strip()
                    # Case-insensitive search
                    category_obj = Category.objects.filter(name__iexact=new_name).first()
                    if not category_obj:
                        category_obj = Category.objects.create(name=new_name.title())
                    category_id = category_obj.id
                else:
                    category_id = raw_category

                # Prepare data for Form validation
                data = {
                    'name': prod_name,
                    'price': request.POST.get(f'prod_{i}_price'),
                    'stocks': request.POST.get(f'prod_{i}_stocks'),
                    'description': prod_desc,
                    'category': category_id,
                    'meetup_spot': request.POST.get(f'prod_{i}_meetup'),
                    'payment_method': request.POST.get(f'prod_{i}_payment'),
                }

                # Temporary form instance for validation
                form = ProductForm(data, {'image': request.FILES.get(f'prod_{i}_image_0')})
                
                if form.is_valid():
                    product = form.save(commit=False)
                    product.seller = request.user
                    product.status = 'Pending' 
                    product.save()

                    image_count = int(request.POST.get(f'prod_{i}_image_count', 0))
                    gallery_imgs = [
                        ProductImage(product=product, image=request.FILES.get(f'prod_{i}_image_{j}'))
                        for j in range(1, image_count)
                        if request.FILES.get(f'prod_{i}_image_{j}')
                    ]
                    # Bulk create gallery images to optimize DB performance
                    ProductImage.objects.bulk_create(gallery_imgs)
                else:
                    # Atomic transaction will automatically rollback all products if one fails
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

