from django.shortcuts import render, redirect
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic import  CreateView, ListView, DetailView
from ..forms import ProductForm
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import Product, Category, ProductImage, Wishlist, CartItem, ProductVariant, MeetupLocation 
from django.http import JsonResponse
import re
import json
from django.db.models import Q

def landing_page(request):
    categories = Category.objects.all()
    products = Product.objects.all() 
    
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)

    return render(request, 'UTrade_app/landingpage.html', {
        'categories': categories,
        'products': products
    })

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
        product.pre_order = form.cleaned_data.get('pre_order') == True or form.cleaned_data.get('pre_order') == "True"
        product.seller = self.request.user
        product.status = 'Pending'
        product.pre_order = form.cleaned_data.get('pre_order', False)
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
                prod_name = request.POST.get(f'prod_{i}_name', '')
                prod_desc = request.POST.get(f'prod_{i}_desc', '')
                prod_price = request.POST.get(f'prod_{i}_price', 0)
                prod_stocks = request.POST.get(f'prod_{i}_stocks', 0)
                raw_category = request.POST.get(f'prod_{i}_category', '')
                raw_meetup = request.POST.get(f'prod_{i}_meetup', '').strip()
                is_pre_order = request.POST.get(f'prod_{i}_pre_order') == 'True'
                raw_pre_order = request.POST.get(f'prod_{i}_pre_order', 'false').lower()
                is_pre_order = raw_pre_order == 'true'
                meetup_obj = None
                if raw_meetup:
                    if raw_meetup.startswith('NEW:'):
                        new_loc_name = raw_meetup.replace('NEW:', '').strip()
                        
                        flagged_loc = self.is_content_prohibited(new_loc_name)
                        if flagged_loc:
                            return JsonResponse({
                                'status': 'error', 
                                'message': f'Meetup location contains prohibited content: {flagged_loc}'
                            }, status=400)

                        meetup_obj, _ = MeetupLocation.objects.get_or_create(
                            name__iexact=new_loc_name,
                            defaults={
                                'name': new_loc_name,
                                'added_by': request.user 
                            }
                        )
                    elif raw_meetup.isdigit():
                        meetup_obj = MeetupLocation.objects.filter(id=int(raw_meetup)).first()
                    else:
                        meetup_obj, _ = MeetupLocation.objects.get_or_create(
                            name__iexact=raw_meetup,
                            defaults={
                                'name': raw_meetup,
                                'added_by': request.user
                            }
                        )

                if self.is_content_prohibited(prod_name) or self.is_content_prohibited(prod_desc):
                    return JsonResponse({'status': 'error', 'message': f'Prohibited content in {prod_name}.'}, status=400)

                category_obj = None
                if raw_category:
                    if raw_category.startswith('NEW:'):
                        new_cat_name = raw_category.replace('NEW:', '').strip()
                        category_obj, _ = Category.objects.get_or_create(
                            name__iexact=new_cat_name, 
                            defaults={'name': new_cat_name.title()}
                        )
                    elif raw_category.isdigit():
                        category_obj = Category.objects.filter(id=int(raw_category)).first()

                prod_payment = request.POST.get(f'prod_{i}_payment', 'BOTH')    
                                         
                new_product = Product.objects.create(
                    name=prod_name,
                    description=prod_desc,
                    category=category_obj,
                    meetup_location=meetup_obj,
                    seller=request.user,
                    pre_order=is_pre_order,
                    accepted_payments=prod_payment,
                    status='Pending'
                )

                saved_images_objects = []
                image_count = int(request.POST.get(f'prod_{i}_image_count', 0))
                
                for j in range(image_count):
                    img_file = request.FILES.get(f'prod_{i}_image_{j}')
                    if img_file:
                        img_obj = ProductImage.objects.create(product=new_product, image=img_file)
                        saved_images_objects.append(img_obj)
                        
                        if j == 0:
                            new_product.image = img_file
                            new_product.save()

                variants_data = request.POST.get(f'prod_{i}_variants', '[]')
                try:
                    variants_list = json.loads(variants_data)
                    
                    if not variants_list:
                        ProductVariant.objects.create(
                            product=new_product,
                            variant_name="Default",
                            price=prod_price,
                            stocks=prod_stocks,
                            condition="Brand New" 
                        )
                    else:
                        for var in variants_list:
                            variant_instance = ProductVariant(
                                product=new_product,
                                variant_name=var.get('name'),
                                stocks=var.get('stock', 0),
                                price=var.get('price', prod_price),
                                condition=var.get('condition', 'Brand New'),    
                                flaws_description=var.get('flaws', '') 
                            )
                            
                            img_idx = var.get('imageIndex')
                            if img_idx is not None and int(img_idx) < len(saved_images_objects):
                                variant_instance.assigned_image = saved_images_objects[int(img_idx)]
                            
                            variant_instance.save()
                            
                except (json.JSONDecodeError, TypeError):
                    pass 

            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            print(f"Error saving product: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        
class ProductDetailView(DetailView):
    model = Product
    template_name = 'Utrade_app/products/actions/product_details.html'
    context_object_name = 'product'

    def get_queryset(self):
        return super().get_queryset().select_related('seller', 'category')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related_products'] = Product.objects.filter(
            category=self.object.category,
            status='Approved'
        ).exclude(id=self.object.id).select_related('seller')[:4] 
        return context

class ProductListView(ListView):
    model = Product
    template_name = 'UTrade_app/marketplace.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        queryset = Product.objects.filter(status='Approved').select_related('category', 'seller')
        
        query = self.request.GET.get('q')
        category_id = self.request.GET.get('category')
        user_type = self.request.GET.get('type') 

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | 
                Q(description__icontains=query) |
                Q(category__name__icontains=query) |
                Q(seller__user_role__icontains=query) |
                Q(seller__organization__icontains=query)
            )

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if user_type == 'management':
            queryset = queryset.filter(seller__user_role__in=['management', 'admin'])
        elif user_type == 'organization':
            queryset = queryset.filter(seller__user_role__in=['organization', 'alumni_assoc', 'officer'])
        elif user_type == 'student':
            queryset = queryset.exclude(seller__user_role__in=['management', 'admin', 'organization', 'alumni_assoc'])

        return queryset.order_by('-created_at').distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['current_category'] = self.request.GET.get('category')
        context['current_type'] = self.request.GET.get('type')
        context['search_query'] = self.request.GET.get('q') 
        
        if self.request.user.is_authenticated:
            context['user_wishlist_ids'] = set(
                Wishlist.objects.filter(user=self.request.user).values_list('product_id', flat=True)
            )
            context['user_cart_ids'] = set(
                CartItem.objects.filter(cart__user=self.request.user).values_list('variant__product_id', flat=True)
            )
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

