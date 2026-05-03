from django.shortcuts import render, redirect
from django.urls import reverse
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.urls import reverse_lazy
from django.views.generic import  CreateView, ListView, DetailView
from ..forms import ProductForm
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import Product, Category, ProductImage, Wishlist, CartItem, ProductVariant, MeetupLocation, ProhibitedWord, StagedProduct, StagedVariant, StagedImage 
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
def prohibited_words_api(request):
    words = list(ProhibitedWord.objects.values_list('word', flat=True))
    return JsonResponse({'prohibited_words': words})
    
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
        
        if flagged_name or flagged_desc:
            word = flagged_name or flagged_desc
            messages.error(self.request, f"Prohibited content detected: {word}")
            return self.form_invalid(form)
            
        product = form.save(commit=False)
        product.seller = self.request.user
        product.status = 'Pending'
        product.pre_order = form.cleaned_data.get('pre_order', False)
        
        # Capture owner_type for standard form submissions
        product.owner_type = self.request.POST.get('owner_type', 'PERSONAL')
        
        product.save()
        return redirect('product.list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['meetup_locations'] = MeetupLocation.objects.all()
        context['staged_items'] = StagedProduct.objects.filter(
            seller=self.request.user, 
            is_submitted=False
        ).prefetch_related('variants', 'images')
        return context
    
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        is_final_submit = request.POST.get('action') == 'submit_staging'
        
        if not is_final_submit:
            # Fallback to standard single-product form submission
            return super().post(request, *args, **kwargs)

        try:
            # 1. Fetch all staged items for this user that haven't been submitted
            staged_items = StagedProduct.objects.filter(
                seller=request.user, 
                is_submitted=False
            ).prefetch_related('variants', 'images')

            if not staged_items.exists():
                return JsonResponse({'status': 'error', 'message': 'No items in staging to submit.'}, status=400)

            for staged_prod in staged_items:
                # 2. Convert StagedProduct -> Product
                new_product = Product.objects.create(
                    name=staged_prod.name,
                    description=staged_prod.description,
                    category=staged_prod.category,
                    # Assuming meetup_locations_list is a string or handle conversion to FK
                    seller=request.user,
                    pre_order=staged_prod.pre_order,
                    accepted_payments=staged_prod.accepted_payments,
                    owner_type=staged_prod.owner_type,
                    status='Pending'
                )

                # 3. Convert StagedImage -> ProductImage
                for staged_img in staged_prod.images.all():
                    new_img = ProductImage.objects.create(
                        product=new_product,
                        image=staged_img.image
                    )
                    # Set the main display image for the Product model
                    if staged_img.is_main:
                        new_product.image = staged_img.image
                        new_product.save()

                # 4. Convert StagedVariant -> ProductVariant
                for v in staged_prod.variants.all():
                    ProductVariant.objects.create(
                        product=new_product,
                        variant_name=v.variant_name,
                        price=v.price,
                        stocks=v.stocks,
                        condition=v.condition,
                        flaws_description=v.flaws
                    )

                staged_prod.is_submitted = True
                staged_prod.save()

            return JsonResponse({'status': 'success', 'redirect_url': reverse('product.list')})

        except Exception as e:
            print(f"Final Submission Error: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'Failed to process staging list.'}, status=500)
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
            queryset = queryset.filter(owner_type='ORGANIZATION')
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

@login_required
@require_POST
def add_to_staging_ajax(request):
    def check_text(text):
        if not text: return None
        banned = ['alcohol', 'drugs', 'beer', 'wine', 'vape', 'tobacco', 'weed'] # and so on...
        clean = re.sub(r'[^a-z]', '', text.lower())
        for word in banned:
            if word in clean: return word
        return None

    if check_text(request.POST.get('name')) or check_text(request.POST.get('description')):
        return JsonResponse({'status': 'error', 'message': 'Prohibited content detected.'}, status=400)


    staged_prod = StagedProduct.objects.create(
        seller=request.user,
        name=request.POST.get('name'),
        description=request.POST.get('description'),
        category_id=request.POST.get('category') if request.POST.get('category').isdigit() else None,
        meetup_locations_list=request.POST.get('location_options'),
        owner_type=request.POST.get('owner_type', 'PERSONAL'),
        accepted_payments=request.POST.get('payment'),
        pre_order=request.POST.get('pre_order') == 'True'
    )


    variants_data = json.loads(request.POST.get('variants', '[]'))
    for v in variants_data:
        StagedVariant.objects.create(
            staged_product=staged_prod,
            variant_name=v['name'],
            price=v['price'],
            stocks=v['stock'],
            condition=v['condition'],
            flaws=v.get('flaws', '')
        )


    images = request.FILES.getlist('images')
    for i, img in enumerate(images):
        StagedImage.objects.create(
            staged_product=staged_prod,
            image=img,
            is_main=(i == 0)
        )

    return JsonResponse({'status': 'success', 'staged_id': staged_prod.id})
def get_staged_product_details(request, staged_id):
    try:
        product = StagedProduct.objects.get(id=staged_id, seller=request.user)
        
        # Prepare variants list
        variants = list(product.variants.values('variant_name', 'price', 'stocks', 'condition', 'flaws'))
        
        images = [{'url': img.image.url, 'is_main': img.is_main} for img in product.images.all()]

        data = {
            'name': product.name,
            'description': product.description,
            'category': product.category.id if product.category else '',
            'locations': product.meetup_locations_list,
            'variants': variants,
            'images': images,
            'payment': product.accepted_payments,
        }
        return JsonResponse(data)
    except StagedProduct.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
def delete_staged_product(request, staged_id):
    if request.method == "POST" or request.method == "DELETE":
        try:
            item = StagedProduct.objects.get(id=staged_id, seller=request.user)
            item.delete()
            return JsonResponse({'status': 'success'})
        except StagedProduct.DoesNotExist:
            return JsonResponse({'error': 'Item not found'}, status=404)