from django.shortcuts import render, redirect
from django.urls import reverse
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import  CreateView, ListView, DetailView
from ..forms import ProductForm
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import Product, Category, ProductImage, Wishlist,Cart, CartItem, ProductVariant, MeetupLocation, ProhibitedWord, StagedProduct, StagedVariant, StagedImage, CategoryAttribute, PreOrderRequest
from django.http import JsonResponse
import re
import json
from django.db.models import Q

def landing_page(request):
    categories = Category.objects.all()
    products = Product.objects.all() 
    meetup_locations = MeetupLocation.objects.all() 
    
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)

    return render(request, 'UTrade_app/landingpage.html', {
        'categories': categories,
        'products': products,
        'meetup_locations': meetup_locations  
    })
def prohibited_words_api(request):
    words = list(ProhibitedWord.objects.values_list('word', flat=True))
    return JsonResponse({'prohibited_words': words})
    
class ProductCreateView(LoginRequiredMixin, CreateView):
    form_class = ProductForm
    template_name = 'Utrade_app/products/add_product.html'
    BANNED_KEYWORDS = [
        'alcohol', 'drugs', 'beer', 'wine', 'vodka', 'whiskey', 
        'ecigarette', 'vape', 'smoke', 'tobacco', 'cigarette',
        'examanswer', 'leakage', 'leak', 'cheating', 'dregs','weed',
    ]
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['meetup_locations'] = MeetupLocation.objects.all()    
        context['categories'] = Category.objects.all()
        context['staged_items'] = StagedProduct.objects.filter(
            seller=self.request.user, 
            is_submitted=False
        )
        return context
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

    def get_or_create_custom_category(self, request):
        """Helper to handle the 'Other' category logic from the request."""
        category_id = request.POST.get('category')
        custom_name = request.POST.get('custom_category_name') 

        if category_id == 'other' and custom_name:
            category, created = Category.objects.get_or_create(
                name=custom_name.strip().title()
            )
            return category
        
        return Category.objects.filter(id=category_id).first()

    def form_valid(self, form):
        name = form.cleaned_data.get('name', '')
        desc = form.cleaned_data.get('description', '')
        
        flagged_name = self.is_content_prohibited(name)
        flagged_desc = self.is_content_prohibited(desc)
        
        if flagged_name or flagged_desc:
            word = flagged_name or flagged_desc
            messages.error(self.request, f"Prohibited content detected: {word}")
            return self.form_invalid(form)
            
        product = form.save(commit=False)
        
        category = self.get_or_create_custom_category(self.request)
        if category:
            product.category = category
        
        product.seller = self.request.user
        product.status = 'Pending'
        product.pre_order = form.cleaned_data.get('pre_order', False)
        product.owner_type = self.request.POST.get('owner_type', 'PERSONAL')
        
        product.save()
        return redirect('product.list')

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        is_final_submit = request.POST.get('action') == 'submit_staging'

        if not is_final_submit:
            return super().post(request, *args, **kwargs)

        try:
            staged_items = StagedProduct.objects.filter(
                seller=request.user,
                is_submitted=False
            ).prefetch_related('variants', 'images')

            if not staged_items.exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'No items in staging to submit.'
                }, status=400)

            for staged_prod in staged_items:
                # 1. Create the Product
                new_product = Product.objects.create(
                    name=staged_prod.name,
                    description=staged_prod.description,
                    category=staged_prod.category,
                    seller=request.user,
                    pre_order=staged_prod.pre_order,
                    accepted_payments=staged_prod.accepted_payments,
                    owner_type=staged_prod.owner_type,
                    status='Pending',
                    # Add this if you have the field on Product:
                    # preferred_meetup_time=getattr(staged_prod, 'preferred_meetup_time', None),
                )

                # 2. Handle SINGLE free-text location
                # staged_prod.meetup_locations_list now holds a single string, e.g. "Library Lobby"
                location_text = (staged_prod.meetup_locations_list or "").strip()

                if location_text:
                    try:
                        # Option A: get_or_create a MeetupLocation by name (keeps M2M)
                        location_obj, _ = MeetupLocation.objects.get_or_create(
                            name=location_text
                        )
                        new_product.meetup_locations.set([location_obj])

                        # Option B (simpler long-term): if you add a CharField on Product:
                        # new_product.meetup_location_text = location_text
                        # new_product.save(update_fields=['meetup_location_text'])
                    except Exception as e:
                        print(f"Error linking location: {e}")

                # 3. Images
                for staged_img in staged_prod.images.all():
                    ProductImage.objects.create(
                        product=new_product,
                        image=staged_img.image,
                        # is_main=staged_img.is_main  # if your model has this
                    )
                    if getattr(staged_img, 'is_main', False):
                        # only if Product still has a single image field
                        if hasattr(new_product, 'image'):
                            new_product.image = staged_img.image
                            new_product.save(update_fields=['image'])

                # 4. Variants (correct indentation – NOT inside the image loop)
                for v in staged_prod.variants.all():
                    ProductVariant.objects.create(
                        product=new_product,
                        variant_name=v.variant_name,
                        price=v.price,
                        stocks=v.stocks,
                        condition=v.condition,
                        flaws_description=getattr(v, 'flaws', '') or getattr(v, 'flaws_description', ''),
                        attribute_value=getattr(v, 'variant_attribute', '') or getattr(v, 'attribute_value', ''),
                    )

                    # Optional: save custom attribute to category
                    attr_value = getattr(v, 'variant_attribute', None) or getattr(v, 'attribute_value', None)
                    if staged_prod.category and attr_value:
                        CategoryAttribute.objects.get_or_create(
                            category=staged_prod.category,
                            value=str(attr_value).strip(),
                            defaults={
                                'is_custom': True,
                                'created_by': request.user
                            }
                        )

                # 5. Mark staged item as submitted
                staged_prod.is_submitted = True
                staged_prod.save(update_fields=['is_submitted'])

            return JsonResponse({
                'status': 'success',
                'redirect_url': reverse('product.create')
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
class ProductDetailView(DetailView):
    model = Product
    template_name = 'Utrade_app/products/product_details.html'
    context_object_name = 'product'

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related('seller', 'category')
            .prefetch_related('variants', 'images')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object

        context['related_products'] = Product.objects.filter(
            category=product.category,
            status='Approved'
        ).exclude(id=product.id).select_related('seller')[:4]

        # Split "Monday,Thursday,Saturday" for the template
        context['available_days_list'] = [
            d.strip()
            for d in (product.available_days or '').split(',')
            if d.strip()
        ]
        return context


class BatchAddToCartView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            items = data.get('items', [])

            if not items:
                return JsonResponse({'success': False, 'message': 'No items selected.'}, status=400)

            cart, _ = Cart.objects.get_or_create(user=request.user)

            for item in items:
                variant_id = item.get('variant_id')
                quantity = int(item.get('quantity', 1))

                variant = ProductVariant.objects.filter(id=variant_id).first()
                if not variant or variant.stocks < quantity:
                    continue

                cart_item, created = CartItem.objects.get_or_create(cart=cart, variant=variant)
                if not created:
                    cart_item.quantity += quantity
                else:
                    cart_item.quantity = quantity
                cart_item.save()

            total_cart_count = cart.items.count()
            return JsonResponse({'success': True, 'cart_count': total_cart_count})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class BatchPreOrderView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            status = data.get('status', 'Pending')

            if not items:
                return JsonResponse({'success': False, 'message': 'No items selected.'}, status=400)

            for item in items:
                variant_id = item.get('variant_id')
                quantity = int(item.get('quantity', 1))

                variant = ProductVariant.objects.filter(id=variant_id).first()
                if variant:
                    PreOrderRequest.objects.create(
                        user=request.user,
                        variant=variant,
                        quantity=quantity,
                        status=status
                    )

            return JsonResponse({'success': True, 'message': 'Pre-orders created successfully.'})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
class ProductListView(ListView):
    model = Product
    template_name = 'UTrade_app/products/marketplace.html'
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
    template_name = 'Utrade_app/products/wishlist.html'
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
    from datetime import datetime

    def check_text(text):
        if not text:
            return None
        banned = ['alcohol', 'drugs', 'beer', 'wine', 'vape', 'tobacco', 'weed']
        clean = re.sub(r'[^a-z]', '', text.lower())
        for word in banned:
            if word in clean:
                return word
        return None

    # ---------- Prohibited content ----------
    if check_text(request.POST.get('name')) or check_text(request.POST.get('description')):
        return JsonResponse(
            {'status': 'error', 'message': 'Prohibited content detected.'},
            status=400
        )

    # ---------- Incoming fields ----------
    location = (request.POST.get('location_options') or '').strip()
    available_days_raw = (request.POST.get('available_days') or '').strip()
    meetup_from = request.POST.get('meetup_time_from')  # "07:30"
    meetup_to = request.POST.get('meetup_time_to')      # "09:00"

    ALLOWED_DAYS = {
        'Monday', 'Tuesday', 'Wednesday',
        'Thursday', 'Friday', 'Saturday'
    }

    # ---------- Location ----------
    if not location:
        return JsonResponse(
            {'status': 'error', 'message': 'Campus meetup spot is required.'},
            status=400
        )

    # ---------- Days ----------
    day_list = [d.strip() for d in available_days_raw.split(',') if d.strip()]
    if not day_list:
        return JsonResponse(
            {'status': 'error', 'message': 'Please select at least one available day (Mon–Sat).'},
            status=400
        )
    if any(d not in ALLOWED_DAYS for d in day_list):
        return JsonResponse(
            {'status': 'error', 'message': 'Invalid day selected. Allowed: Monday–Saturday.'},
            status=400
        )

    # ---------- Time range helpers ----------
    def parse_time(value):
        if not value:
            return None
        return datetime.strptime(value, "%H:%M").time()

    def is_within_allowed(t):
        """7:00 AM – 9:00 PM inclusive"""
        if t is None:
            return False
        minutes = t.hour * 60 + t.minute
        return 7 * 60 <= minutes <= 21 * 60

    try:
        t_from = parse_time(meetup_from)
        t_to = parse_time(meetup_to)
    except ValueError:
        return JsonResponse(
            {'status': 'error', 'message': 'Invalid time format. Use HH:MM.'},
            status=400
        )

    if not t_from or not t_to:
        return JsonResponse(
            {'status': 'error', 'message': 'Meetup time range is required.'},
            status=400
        )

    if not is_within_allowed(t_from):
        return JsonResponse(
            {'status': 'error', 'message': 'From time must be between 7:00 AM and 9:00 PM.'},
            status=400
        )

    if not is_within_allowed(t_to):
        return JsonResponse(
            {'status': 'error', 'message': 'To time must be between 7:00 AM and 9:00 PM.'},
            status=400
        )

    if t_from >= t_to:
        return JsonResponse(
            {'status': 'error', 'message': 'From time must be earlier than To time.'},
            status=400
        )

    # ---------- Category (including "other") ----------
    category_id = request.POST.get('category')
    category = None
    if category_id and str(category_id).isdigit():
        category = Category.objects.filter(id=category_id).first()
    elif category_id == 'other':
        custom_name = (request.POST.get('custom_category_name') or '').strip()
        if custom_name:
            category, _ = Category.objects.get_or_create(name=custom_name.title())

    # ---------- Create staged product ----------
    staged_prod = StagedProduct.objects.create(
        seller=request.user,
        name=request.POST.get('name'),
        description=request.POST.get('description'),
        category=category,
        meetup_locations_list=location,                 # single string
        available_days=','.join(day_list),              # "Monday,Thursday"
        preferred_meetup_time_from=t_from,
        preferred_meetup_time_to=t_to,
        owner_type=request.POST.get('owner_type', 'PERSONAL'),
        accepted_payments=request.POST.get('payment') or 'BOTH',
        pre_order=request.POST.get('pre_order') == 'True',
    )

    # ---------- Variants ----------
    try:
        variants_data = json.loads(request.POST.get('variants', '[]'))
    except json.JSONDecodeError:
        variants_data = []

    for v in variants_data:
        StagedVariant.objects.create(
            staged_product=staged_prod,
            variant_name=v.get('name', ''),
            variant_attribute=v.get('attribute', ''),
            price=v.get('price', 0) or 0,
            stocks=v.get('stock', 0) or 0,
            condition=v.get('condition', 'Brand New'),
            flaws=v.get('flaws', ''),
        )

    # ---------- Images ----------
    images = request.FILES.getlist('images')
    for i, img in enumerate(images):
        StagedImage.objects.create(
            staged_product=staged_prod,
            image=img,
            is_main=(i == 0),
        )

    return JsonResponse({
        'status': 'success',
        'staged_id': staged_prod.id
    })
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
            'locations': product.meetup_locations_list or '',
            'available_days': product.available_days or '',
            'meetup_time_from': product.preferred_meetup_time_from.strftime('%H:%M') if product.preferred_meetup_time_from else '',
            'meetup_time_to': product.preferred_meetup_time_to.strftime('%H:%M') if product.preferred_meetup_time_to else '',
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
def get_attributes(request, category_id):
    attributes = CategoryAttribute.objects.filter(category_id=category_id).values('value', 'attribute_type')
    return JsonResponse({'attributes': list(attributes)})