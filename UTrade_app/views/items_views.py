from django.shortcuts import render, redirect
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic import  CreateView, ListView, DetailView
from ..forms import ProductForm
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import Product, Category, ProductImage, Wishlist, CartItem, ProductVariant 
from django.http import JsonResponse
import re
import json

def landing_page(request):
    return render(request, 'UTrade_app/landingpage.html')

class ProductCreateView(LoginRequiredMixin, CreateView):
    form_class = ProductForm
    template_name = 'Utrade_app/products/actions/addproduct.html'
    BANNED_KEYWORDS = [
        'alcohol', 'drugs', 'beer', 'wine', 'vodka', 'whiskey', 
        'ecigarette', 'vape', 'smoke', 'tobacco', 'cigarette',
        'examanswer', 'leakage', 'leak', 'cheating', 'dregs','weed',
    ]

    def is_content_prohibited(self, text):
        if not text: return None
        translations = {'4':'a', '@':'a', '1':'i', '!':'i', '3':'e', '0':'o', '5':'s', '$':'s', '7':'t', '8':'b'}
        text = text.lower()
        for char, replacement in translations.items():
            text = text.replace(char, replacement)
        clean_text = re.sub(r'[^a-z]', '', text)
        for word in self.BANNED_KEYWORDS:
            if word in clean_text:
                return word
        return None

    def form_valid(self, form):
        # handle single form submittions
        name = form.cleaned_data.get('name', '')
        desc = form.cleaned_data.get('description', '')
        category = form.cleaned_data.get('category') 
        
        flagged_name = self.is_content_prohibited(name)
        flagged_desc = self.is_content_prohibited(desc)
        f_cat = self.is_content_prohibited(category.name) if category else None
        
        if flagged_name or flagged_desc:
            word = flagged_name or flagged_desc
            messages.error(self.request, f"Prohibited content detected: {word}")
            return self.form_invalid(form)
            
        product = form.save(commit=False)
        product.seller = self.request.user
        product.status = 'Pending'
        product.save()
        return redirect('product.list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context
    
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        total_products = int(request.POST.get('total_products', 0))
        
        if total_products == 0:
            return super().post(request, *args, **kwargs)

        try:
            for i in range(total_products):
                # 1. Basic Data Extraction
                prod_name = request.POST.get(f'prod_{i}_name', '')
                prod_desc = request.POST.get(f'prod_{i}_desc', '')
                prod_price = request.POST.get(f'prod_{i}_price', 0)
                prod_stocks = request.POST.get(f'prod_{i}_stocks', 0)
                raw_category = request.POST.get(f'prod_{i}_category', '')
                
                if self.is_content_prohibited(prod_name) or self.is_content_prohibited(prod_desc):
                    return JsonResponse({'status': 'error', 'message': f'Prohibited content in {prod_name}.'}, status=400)

                # 2. Category Handling
                if raw_category.startswith('NEW:'):
                    new_name = raw_category.replace('NEW:', '').strip()
                    category_obj, _ = Category.objects.get_or_create(
                        name__iexact=new_name, 
                        defaults={'name': new_name.title()}
                    )
                else:
                    category_obj = Category.objects.filter(id=raw_category).first()

                # 3. Create Product
                new_product = Product.objects.create(
                    name=prod_name,
                    description=prod_desc,
                    category=category_obj,
                    seller=request.user,
                    status='Pending'
                )

                # 4. CRITICAL: Handle ALL images first and store them in a list
                # This list maps exactly to the 'selectedFiles' indices in your JavaScript
                saved_images_objects = []
                image_count = int(request.POST.get(f'prod_{i}_image_count', 0))
                
                for j in range(image_count):
                    img_file = request.FILES.get(f'prod_{i}_image_{j}')
                    if img_file:
                        # Save to ProductImage table
                        img_obj = ProductImage.objects.create(product=new_product, image=img_file)
                        saved_images_objects.append(img_obj)
                        
                        # Set the very first image as the main Product cover
                        if j == 0:
                            new_product.image = img_file
                            new_product.save()

                # 5. Handle Variants (Now that images exist in DB)
                variants_data = request.POST.get(f'prod_{i}_variants', '[]')
                try:
                    variants_list = json.loads(variants_data)
                    
                    if not variants_list:
                        ProductVariant.objects.create(
                            product=new_product,
                            variant_name="Default",
                            price=prod_price,
                            stocks=prod_stocks
                        )
                    else:
                        for var in variants_list:
                            # Create variant instance without saving yet
                            variant_instance = ProductVariant(
                                product=new_product,
                                variant_name=var.get('name'),
                                stocks=var.get('stock', 0),
                                price=var.get('price', prod_price)
                            )
                            
                            # Link the assigned image using the index from JS
                            img_idx = var.get('imageIndex')
                            if img_idx is not None:
                                try:
                                    # Match index to our saved_images_objects list
                                    variant_instance.assigned_image = saved_images_objects[int(img_idx)]
                                except (IndexError, ValueError, TypeError):
                                    variant_instance.assigned_image = None
                            
                            variant_instance.save()
                            
                except (json.JSONDecodeError, TypeError):
                    pass 

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
        queryset = Product.objects.filter(status='Approved').select_related('category') 
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['current_category'] = self.request.GET.get('category')
        
        if self.request.user.is_authenticated:
            user_wishlist = Wishlist.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            context['user_wishlist_ids'] = set(user_wishlist)
            
            user_cart = CartItem.objects.filter(cart__user=self.request.user).values_list('variant__product_id', flat=True)
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

