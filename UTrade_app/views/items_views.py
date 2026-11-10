from django.shortcuts import render, redirect
from django.urls import reverse
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, DetailView
from ..forms import ProductForm
from decimal import Decimal, InvalidOperation
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models import (
       Product, Category, ProductImage, Wishlist, Cart, CartItem,
       ProductVariant, MeetupLocation, ProhibitedWord, StagedProduct,
       StagedVariant, StagedImage, CategoryAttribute, PreOrderRequest,
       Organization, Review, SellerReview,
   )
from django.http import JsonResponse
from django.utils import timezone
import re
import json
from django.db.models import Q, F, Min, Sum, Count


User = get_user_model()

CBRGU_ROLES = ('management', 'cbrgu_staff')

def get_seller(self):
    return get_object_or_404(User, pk=self.kwargs['seller_id'])


# ===================== PRODUCT CODE =====================
def generate_next_product_code():
    """
    Auto code format: UTR-YYYY-####
    Example: UTR-2026-0042
    Increments from the highest sequence used on Product + StagedProduct for the current year.
    """
    year = timezone.now().year
    prefix = f'UTR-{year}-'

    def max_seq(queryset):
        best = 0
        for code in queryset.filter(product_code__startswith=prefix).values_list('product_code', flat=True):
            if not code:
                continue
            m = re.search(r'(\d+)$', code)
            if m:
                best = max(best, int(m.group(1)))
        return best

    last = max(
        max_seq(Product.objects.all()),
        max_seq(StagedProduct.objects.all()),
    )
    return f'{prefix}{last + 1:04d}'


# ===================== ORG LOOKUP + APPROVAL LETTER (on Product) =====================
def _get_user_organization(user):
    """
    Return the Organization instance linked to this user, or None.
    Used only for context display – approval_letter is NOT on Organization.
    """
    if not getattr(user, 'is_officer', False):
        return None

    org = getattr(user, 'organization', None)
    if org is not None and hasattr(org, 'pk'):
        return org

    if isinstance(org, str) and org.strip():
        return (
            Organization.objects.filter(name=org).first()
            or Organization.objects.filter(course_code=org).first()
        )

    if isinstance(org, int):
        return Organization.objects.filter(pk=org).first()

    for attr in ('org', 'org_link', 'related_org'):
        candidate = getattr(user, attr, None)
        if candidate is not None and hasattr(candidate, 'pk'):
            return candidate

    return None


def _validate_approval_letter_file(file):
    """
    Validate an uploaded approval-letter file (JPG/PNG, max 10 MB).
    Returns (ok: bool, message: str|None).
    Does NOT touch Organization – letter belongs on Product / StagedProduct.
    """
    if not file:
        return True, None

    allowed_types = {'image/jpeg', 'image/png', 'image/jpg'}
    if (
        file.content_type not in allowed_types
        and not file.name.lower().endswith(('.jpg', '.jpeg', '.png'))
    ):
        return False, 'Only JPG or PNG files are allowed.'

    if file.size > 10 * 1024 * 1024:
        return False, 'File exceeds the 10 MB limit.'

    return True, None
# ===================== IMAGES, SIZES AND SIZE TABLE =====================
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_SIZE_ROWS = 20
MAX_SIZE_COLUMNS = 8
MAX_VARIANTS = 30


def _validate_image_file(file, label='Image'):
    """JPG / PNG / WEBP, max 10 MB. Returns (ok, message)."""
    if not file:
        return True, None
    content_type = (getattr(file, 'content_type', '') or '').lower()
    name = (file.name or '').lower()
    if (
        content_type not in {'image/jpeg', 'image/jpg', 'image/png', 'image/webp'}
        and not name.endswith(('.jpg', '.jpeg', '.png', '.webp'))
    ):
        return False, f'{label} must be a JPG, PNG or WEBP image.'
    if file.size > MAX_IMAGE_BYTES:
        return False, f'{label} exceeds the 10 MB limit.'
    return True, None


def _clean_text(value, limit):
    return re.sub(r'\s+', ' ', str(value or '')).strip()[:limit]


def _clean_sizes(raw):
    """Unique size labels, 20 characters each."""
    seen, out = set(), []
    for item in raw or []:
        size = _clean_text(item, 20)
        if size and size.lower() not in seen:
            seen.add(size.lower())
            out.append(size)
    return out


def _split_sizes(text):
    return _clean_sizes((text or '').split(','))


def _clean_size_chart(raw):
    """
    Validate and tidy the size table sent by the browser:
    {"columns": ["Height (cm)", ...], "rows": [{"size": "S", "values": ["160", ...]}]}
    Returns a clean dict, or None when there is nothing usable.
    """
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    columns, kept = [], []
    for index, column in enumerate(data.get('columns') or []):
        column = _clean_text(column, 30)
        if (
            column
            and column.lower() not in [c.lower() for c in columns]
            and len(columns) < MAX_SIZE_COLUMNS
        ):
            columns.append(column)
            kept.append(index)

    rows, seen = [], set()
    for row in (data.get('rows') or [])[:MAX_SIZE_ROWS]:
        if not isinstance(row, dict):
            continue
        size = _clean_text(row.get('size'), 20)
        if not size or size.lower() in seen:
            continue
        seen.add(size.lower())
        values = row.get('values') or []
        rows.append({
            'size': size,
            'values': [
                _clean_text(values[i] if i < len(values) else '', 20) for i in kept
            ],
        })

    if not columns or not rows:
        return None
    return {'columns': columns, 'rows': rows}

# ===================== LANDING / HELPERS =====================
def landing_page(request):
    categories = Category.objects.all().order_by('name')
    meetup_locations = MeetupLocation.objects.all()

    products = (
        Product.objects.filter(status='Approved')
        .select_related('category', 'seller', 'related_org')
        .prefetch_related('images', 'variants')
        .order_by('-created_at')
    )

    query = request.GET.get('q')
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
            | Q(product_code__icontains=query)
        )

    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)

    featured_products = products[:12]

    return render(
        request,
        'UTrade_app/landingpage.html',
        {
            'categories': categories,
            'products': featured_products,
            'meetup_locations': meetup_locations,
            'search_query': query,
            'current_category': category_id,
        },
    )


def prohibited_words_api(request):
    words = list(ProhibitedWord.objects.values_list('word', flat=True))
    return JsonResponse({'prohibited_words': words})


@login_required
def next_product_code_api(request):
    """Return the next available product code (for refreshing the form after staging)."""
    return JsonResponse({'product_code': generate_next_product_code()})


# ===================== PRODUCT CREATE (WORKSHOP) =====================
class ProductCreateView(LoginRequiredMixin, CreateView):
    form_class = ProductForm
    template_name = 'UTrade_app/products/add_product.html'

    BANNED_KEYWORDS = [
        'alcohol', 'drugs', 'beer', 'wine', 'vodka', 'whiskey',
        'ecigarette', 'vape', 'smoke', 'tobacco', 'cigarette',
        'examanswer', 'leakage', 'leak', 'cheating', 'dregs', 'weed',
    ]

    def _get_user_organization(self, user):
        return _get_user_organization(user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['meetup_locations'] = MeetupLocation.objects.all()
        context['categories'] = Category.objects.all()
        context['staged_items'] = StagedProduct.objects.filter(
            seller=self.request.user,
            is_submitted=False,
        ).prefetch_related('images', 'variants')
        context['next_product_code'] = generate_next_product_code()
        context['organization'] = self._get_user_organization(self.request.user)
        return context

    def is_content_prohibited(self, text):
        if not text:
            return None
        translations = {
            '4': 'a', '@': 'a', '1': 'i', '!': 'i', '3': 'e',
            '0': 'o', '5': 's', '$': 's', '7': 't', '8': 'b',
        }
        text = text.lower()
        for char, replacement in translations.items():
            text = text.replace(char, replacement)
        clean_text = re.sub(r'[^a-z]', '', text)
        for word in self.BANNED_KEYWORDS:
            if word in clean_text:
                return word
        return None

    def get_or_create_custom_category(self, request):
        category_id = request.POST.get('category')
        if not category_id or category_id == 'other':
            return None
        return Category.objects.filter(id=category_id).first()

    def form_valid(self, form):
        name = form.cleaned_data.get('name', '')
        desc = form.cleaned_data.get('description', '')

        flagged_name = self.is_content_prohibited(name)
        flagged_desc = self.is_content_prohibited(desc)

        if flagged_name or flagged_desc:
            word = flagged_name or flagged_desc
            messages.error(self.request, f'Prohibited content detected: {word}')
            return self.form_invalid(form)

        product = form.save(commit=False)

        category = self.get_or_create_custom_category(self.request)
        if category:
            product.category = category

        product.seller = self.request.user
        product.status = 'Pending'
        product.pre_order = form.cleaned_data.get('pre_order', False)
        product.owner_type = self.request.POST.get('owner_type', 'PERSONAL')

        selected_location = self.request.POST.get('location_options', '').strip()
        if selected_location:
            product.meetup_location_text = selected_location

        if not getattr(product, 'product_code', None):
            product.product_code = generate_next_product_code()

        product.save()
        return redirect('product.list')

    # ------------------------------------------------------------------
    # POST – final staging submit; letter goes onto each Product
    # ------------------------------------------------------------------
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        is_final_submit = request.POST.get('action') == 'submit_staging'

        if not is_final_submit:
            return super().post(request, *args, **kwargs)

        # Validate any freshly uploaded letter (does not touch Organization)
        letter_file = request.FILES.get('approval_letter')
        ok, msg = _validate_approval_letter_file(letter_file)
        if not ok:
            return JsonResponse({'status': 'error', 'message': msg}, status=400)

        try:
            staged_items = StagedProduct.objects.filter(
                seller=request.user,
                is_submitted=False,
            ).prefetch_related('variants', 'images')

            if not staged_items.exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'No items in staging to submit.',
                }, status=400)

            # Officers must supply a letter (request file OR already on a staged item)
            if getattr(request.user, 'is_officer', False):
                has_letter = bool(letter_file)
                if not has_letter:
                    for sp in staged_items:
                        if getattr(sp, 'approval_letter', None):
                            has_letter = True
                            break
                if not has_letter:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Letter of Approval is required.',
                    }, status=400)

            for staged_prod in staged_items:
                product_code = (getattr(staged_prod, 'product_code', None) or '').strip()
                if (
                    not product_code
                    or Product.objects.filter(product_code=product_code).exists()
                ):
                    product_code = generate_next_product_code()

                location_text = (
                    getattr(staged_prod, 'meetup_locations_list', '')
                    or request.POST.get('location_options', '')
                ).strip()

                new_product = Product.objects.create(
                    name=staged_prod.name,
                    description=staged_prod.description,
                    category=staged_prod.category,
                    seller=request.user,
                    pre_order=staged_prod.pre_order,
                    accepted_payments=staged_prod.accepted_payments,
                    owner_type=staged_prod.owner_type,
                    status='Pending',
                    product_code=product_code,
                    meetup_location_text=location_text,
                    available_days=getattr(staged_prod, 'available_days', '') or '',
                    preferred_meetup_time_from=getattr(
                        staged_prod, 'preferred_meetup_time_from', None
                    ),
                    preferred_meetup_time_to=getattr(
                        staged_prod, 'preferred_meetup_time_to', None
                    ),
                    size_chart=getattr(staged_prod, 'size_chart', None),
                )

                # ----- Attach approval letter to the PRODUCT -----
                letter_to_use = letter_file or getattr(staged_prod, 'approval_letter', None)
                if letter_to_use and hasattr(new_product, 'approval_letter'):
                    new_product.approval_letter = letter_to_use
                    new_product.save(update_fields=['approval_letter'])

                # Optional MeetupLocation M2M
                if location_text and hasattr(new_product, 'meetup_locations'):
                    try:
                        location_obj, _ = MeetupLocation.objects.get_or_create(
                            name=location_text
                        )
                        new_product.meetup_locations.set([location_obj])
                    except Exception as e:
                        print(f'Error linking location: {e}')

                # Cover photo (older staged items may still have several images)
                for staged_img in staged_prod.images.all():
                    ProductImage.objects.create(
                        product=new_product,
                        image=staged_img.image,
                    )
                    if getattr(staged_img, 'is_main', False) and hasattr(new_product, 'image'):
                        new_product.image = staged_img.image
                        new_product.save(update_fields=['image'])

                # Variations
                for v in staged_prod.variants.all():
                    sizes_text = (
                        getattr(v, 'variant_attribute', None)
                        or getattr(v, 'attribute_value', None)
                        or ''
                    )
                    variant = ProductVariant.objects.create(
                        product=new_product,
                        variant_name=v.variant_name,
                        price=v.price,
                        stocks=v.stocks,
                        condition=v.condition or 'Brand New',
                        flaws_description=(
                            getattr(v, 'flaws', '')
                            or getattr(v, 'flaws_description', '')
                            or ''
                        ),
                        attribute_value=sizes_text,
                    )

                    # The variation's own image becomes its assigned image
                    variant_image = getattr(v, 'image', None)
                    if variant_image:
                        product_image = ProductImage.objects.create(
                            product=new_product,
                            image=variant_image,
                            variant=variant,
                        )
                        variant.assigned_image = product_image
                        variant.save(update_fields=['assigned_image'])

                    # Remember each size as a quick-select suggestion for the category
                    if staged_prod.category:
                        for size in _split_sizes(sizes_text):
                            CategoryAttribute.objects.get_or_create(
                                category=staged_prod.category,
                                value=size[:50],
                                defaults={
                                    'is_custom': True,
                                    'created_by': request.user,
                                },
                            )

                staged_prod.is_submitted = True
                staged_prod.save(update_fields=['is_submitted'])

            return JsonResponse({
                'status': 'success',
                'redirect_url': reverse('product.create'),
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e),
            }, status=500)


# ===================== PRODUCT DETAIL / LIST / CART / ETC. =====================
class ProductDetailView(DetailView):
    model = Product
    template_name = 'UTrade_app/products/product_details.html'
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
            status='Approved',
        ).exclude(id=product.id).select_related('seller')[:4]

        context['available_days_list'] = [
            d.strip()
            for d in (product.available_days or '').split(',')
            if d.strip()
        ]

        reviews = getattr(product, 'reviews', None)
        if reviews is not None:
            context['reviews'] = reviews.select_related('user').order_by('-created_at')[:20]
        else:
            from ..models import Review
            context['reviews'] = Review.objects.filter(
                Q(product=product) | Q(order_item__product_variant__product=product)
            ).select_related('user').order_by('-created_at')[:20]

        context['in_wishlist'] = False
        if self.request.user.is_authenticated:
            context['in_wishlist'] = Wishlist.objects.filter(
                user=self.request.user, product=product
            ).exists()

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
                        buyer=request.user,
                        product_variant=variant,
                        seller=variant.product.seller,
                        quantity=quantity,
                        status=status,
                    )

            return JsonResponse({'success': True, 'message': 'Pre-orders created successfully.'})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class ProductListView(ListView):
    model = Product
    template_name = 'UTrade_app/products/marketplace.html'
    context_object_name = 'products'
    paginate_by = 15

    def get_queryset(self):
        queryset = (
            Product.objects.filter(status='Approved')
            .select_related('category', 'seller', 'related_org')
            .prefetch_related('images', 'variants')
        )

        query = self.request.GET.get('q')
        category_id = self.request.GET.get('category')
        org_id = self.request.GET.get('org')
        user_type = self.request.GET.get('type')
        sort = self.request.GET.get('sort')

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(category__name__icontains=query)
                | Q(seller__user_role__icontains=query)
                | Q(product_code__icontains=query)
                | Q(related_org__name__icontains=query)
                | Q(related_org__full_name__icontains=query)
            )

            if query.isdigit():
                queryset = queryset | Product.objects.filter(id=int(query), status='Approved')

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if org_id:
            queryset = queryset.filter(
                Q(related_org_id=org_id)
                | Q(seller__org_link_id=org_id)
                | Q(owner_type='ORGANIZATION', seller__org_link_id=org_id)
            )

        if user_type == 'management':
            queryset = queryset.filter(
                Q(owner_type='MANAGEMENT')
                | Q(seller__user_role__in=['management', 'admin', 'campus_admin'])
            )
        elif user_type == 'organization' and not org_id:
            queryset = queryset.filter(
                Q(owner_type='ORGANIZATION')
                | Q(related_org__isnull=False)
                | Q(seller__org_link__isnull=False)
            )
        elif user_type == 'student':
            queryset = queryset.exclude(
                Q(owner_type__in=['MANAGEMENT', 'ORGANIZATION'])
                | Q(seller__user_role__in=[
                    'management', 'admin', 'campus_admin',
                    'org_officer', 'alumni_assoc',
                ])
            )

        # Sorting
        if sort == 'price_low':
            queryset = queryset.annotate(min_price=Min('variants__price')).order_by('min_price', '-created_at')
        elif sort == 'price_high':
            queryset = queryset.annotate(min_price=Min('variants__price')).order_by(
                F('min_price').desc(nulls_last=True), '-created_at'
            )
        else:
            queryset = queryset.order_by('-created_at')

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        category = self.request.GET.get('category')
        org = self.request.GET.get('org')
        user_type = self.request.GET.get('type')

        context['categories'] = Category.objects.all().order_by('name')
        context['organizations'] = Organization.objects.all().order_by('name')

        context['current_category'] = category
        context['current_org'] = org
        context['current_type'] = user_type
        context['current_sort'] = self.request.GET.get('sort') or ''
        context['search_query'] = self.request.GET.get('q')

        # Objects behind the active filters (for the title and the removable chips)
        context['current_category_obj'] = (
            Category.objects.filter(pk=category).first() if category and category.isdigit() else None
        )
        context['current_org_obj'] = (
            Organization.objects.filter(pk=org).first() if org and org.isdigit() else None
        )
        context['active_filter_count'] = sum(1 for v in (category, org, user_type) if v)

        # Query string without ?page= so pagination keeps every filter and the sort
        params = self.request.GET.copy()
        params.pop('page', None)
        context['querystring'] = params.urlencode()

        if self.request.user.is_authenticated:
            context['user_wishlist_ids'] = set(
                Wishlist.objects.filter(
                    user=self.request.user,
                    product__isnull=False
                ).values_list('product_id', flat=True)
            )
            context['user_cart_ids'] = set(
                CartItem.objects.filter(
                    cart__user=self.request.user,
                    variant__isnull=False,
                    variant__product__isnull=False
                ).values_list('variant__product_id', flat=True)
            )
        else:
            context['user_wishlist_ids'] = set()
            context['user_cart_ids'] = set()

        return context

class WishlistListView(LoginRequiredMixin, ListView):
    model = Wishlist
    template_name = 'UTrade_app/products/wishlist.html'
    context_object_name = 'wishlists'

    def get_queryset(self):
        return (
            Wishlist.objects.filter(user=self.request.user)
            .select_related('product')
            .order_by('-added_at')
        )


@login_required
def toggle_wishlist(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        wishlist_item, created = Wishlist.objects.get_or_create(
            user=request.user, product=product
        )

        if not created:
            wishlist_item.delete()
            status = 'removed'
        else:
            status = 'added'

        return JsonResponse({'status': 'success', 'action': status})
    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Product not found'})


# ===================== STAGING AJAX ENDPOINTS =====================
@login_required
@require_POST
def add_to_staging_ajax(request):
    """
    Create a StagedProduct from the workshop form. ALWAYS returns JSON.

      cover              the single cover photo (or keep_cover_id when editing)
      variants           [{name, sizes[], price, stock, keepFrom}] as JSON, plus an
                         optional variant_image_<index> file for each variation
      size_chart         optional size table (JSON)
      editing_id         replaces that staged item; its images are carried over
    """
    from datetime import datetime

    def fail(message, status=400):
        return JsonResponse({'status': 'error', 'message': message}, status=status)

    try:
        def check_text(text):
            if not text:
                return None
            banned = ['alcohol', 'drugs', 'beer', 'wine', 'vape', 'tobacco', 'weed']
            clean = re.sub(r'[^a-z]', '', text.lower())
            for word in banned:
                if word in clean:
                    return word
            return None

        if check_text(request.POST.get('name')) or check_text(request.POST.get('description')):
            return fail('Prohibited content detected.')

        letter_file = request.FILES.get('approval_letter')
        ok, msg = _validate_approval_letter_file(letter_file)
        if not ok:
            return fail(msg)

        location = (request.POST.get('location_options') or '').strip()
        available_days_raw = (request.POST.get('available_days') or '').strip()
        meetup_from = request.POST.get('meetup_time_from')
        meetup_to = request.POST.get('meetup_time_to')
        product_code = (request.POST.get('product_code') or '').strip()

        ALLOWED_DAYS = {
            'Monday', 'Tuesday', 'Wednesday',
            'Thursday', 'Friday', 'Saturday',
        }

        if not location:
            return fail('Campus meetup spot is required.')

        day_list = [d.strip() for d in available_days_raw.split(',') if d.strip()]
        if not day_list:
            return fail('Please select at least one available day (Mon–Sat).')
        if any(d not in ALLOWED_DAYS for d in day_list):
            return fail('Invalid day selected. Allowed: Monday–Saturday.')

        def parse_time(value):
            if not value:
                return None
            return datetime.strptime(value, '%H:%M').time()

        def is_within_allowed(t):
            if t is None:
                return False
            minutes = t.hour * 60 + t.minute
            return 7 * 60 <= minutes <= 21 * 60

        try:
            t_from = parse_time(meetup_from)
            t_to = parse_time(meetup_to)
        except ValueError:
            return fail('Invalid time format. Use HH:MM.')

        if not t_from or not t_to:
            return fail('Meetup time range is required.')
        if not is_within_allowed(t_from):
            return fail('From time must be between 7:00 AM and 9:00 PM.')
        if not is_within_allowed(t_to):
            return fail('To time must be between 7:00 AM and 9:00 PM.')
        if t_from >= t_to:
            return fail('From time must be earlier than To time.')

        # ---------------- variations ----------------
        try:
            variants_data = json.loads(request.POST.get('variants', '[]'))
        except json.JSONDecodeError:
            variants_data = []
        if not isinstance(variants_data, list) or not variants_data:
            return fail('Add at least one variation.')
        if len(variants_data) > MAX_VARIANTS:
            return fail(f'You can add up to {MAX_VARIANTS} variations.')

        parsed_variants = []
        for index, v in enumerate(variants_data):
            if not isinstance(v, dict):
                return fail('Invalid variation data.')

            name = _clean_text(v.get('name'), 100)
            if not name:
                return fail('Every variation needs a name.')

            try:
                price = Decimal(str(v.get('price'))).quantize(Decimal('0.01'))
            except (InvalidOperation, ValueError, TypeError):
                return fail(f'Invalid price for "{name}".')
            if not (Decimal('0') < price < Decimal('100000000')):
                return fail(f'The price for "{name}" must be greater than 0.')

            try:
                stock = int(v.get('stock'))
            except (TypeError, ValueError):
                return fail(f'Invalid stock for "{name}".')
            if stock < 0 or stock > 100000:
                return fail(f'Invalid stock for "{name}".')

            sizes_text = ', '.join(_clean_sizes(v.get('sizes')))
            if len(sizes_text) > 100:
                return fail(f'Too many sizes for "{name}". Keep the list under 100 characters.')

            image_file = request.FILES.get(f'variant_image_{index}')
            ok, msg = _validate_image_file(image_file, f'The image for "{name}"')
            if not ok:
                return fail(msg)

            keep_from = str(v.get('keepFrom') or '')
            parsed_variants.append({
                'name': name,
                'price': price,
                'stock': stock,
                'sizes_text': sizes_text,
                'image_file': image_file,
                'keep_from': int(keep_from) if keep_from.isdigit() else None,
            })

        # ---------------- cover photo ----------------
        cover_file = request.FILES.get('cover')
        ok, msg = _validate_image_file(cover_file, 'The cover photo')
        if not ok:
            return fail(msg)

        editing_id = str(request.POST.get('editing_id') or '')
        old = None
        if editing_id.isdigit():
            old = StagedProduct.objects.filter(
                pk=int(editing_id), seller=request.user, is_submitted=False
            ).first()

        keep_cover_id = str(request.POST.get('keep_cover_id') or '')
        keep_cover_row = None
        if old and not cover_file and keep_cover_id.isdigit():
            keep_cover_row = old.images.filter(pk=int(keep_cover_id)).first()
        if not cover_file and not keep_cover_row:
            return fail('A cover photo is required.')

        category_id = request.POST.get('category')
        category = None
        if category_id and str(category_id).isdigit():
            category = Category.objects.filter(id=category_id).first()

        replaced_id = old.id if old else None

        with transaction.atomic():
            keep_cover_name = (
                keep_cover_row.image.name if keep_cover_row and keep_cover_row.image else ''
            )
            keep_variant_images = {}
            keep_letter_name = ''
            if old:
                keep_variant_images = {
                    sv.pk: sv.image.name for sv in old.variants.all() if sv.image
                }
                keep_letter_name = old.approval_letter.name if old.approval_letter else ''
                if not product_code:
                    product_code = old.product_code or ''
                old.delete()          # files stay in storage; the new item re-uses them

            if (
                not product_code
                or Product.objects.filter(product_code=product_code).exists()
                or StagedProduct.objects.filter(product_code=product_code).exists()
            ):
                product_code = generate_next_product_code()

            staged_prod = StagedProduct.objects.create(
                seller=request.user,
                name=_clean_text(request.POST.get('name'), 255),
                description=request.POST.get('description') or '',
                category=category,
                product_code=product_code,
                meetup_locations_list=location,
                available_days=','.join(day_list),
                preferred_meetup_time_from=t_from,
                preferred_meetup_time_to=t_to,
                owner_type=request.POST.get('owner_type', 'PERSONAL'),
                accepted_payments=request.POST.get('payment') or 'BOTH',
                pre_order=str(request.POST.get('pre_order')).lower() in ['true', 'on', '1', 'yes'],
                size_chart=_clean_size_chart(request.POST.get('size_chart')),
            )

            if letter_file and hasattr(staged_prod, 'approval_letter'):
                staged_prod.approval_letter = letter_file
                staged_prod.save(update_fields=['approval_letter'])
            elif keep_letter_name and hasattr(staged_prod, 'approval_letter'):
                staged_prod.approval_letter = keep_letter_name
                staged_prod.save(update_fields=['approval_letter'])

            for item in parsed_variants:
                staged_variant = StagedVariant(
                    staged_product=staged_prod,
                    variant_name=item['name'],
                    variant_attribute=item['sizes_text'],
                    price=item['price'],
                    stocks=item['stock'],
                    condition='Brand New',
                    flaws='',
                )
                if item['image_file']:
                    staged_variant.image = item['image_file']
                elif item['keep_from'] in keep_variant_images:
                    staged_variant.image = keep_variant_images[item['keep_from']]
                staged_variant.save()

            if cover_file:
                StagedImage.objects.create(
                    staged_product=staged_prod, image=cover_file, is_main=True
                )
            elif keep_cover_name:
                StagedImage.objects.create(
                    staged_product=staged_prod, image=keep_cover_name, is_main=True
                )

        return JsonResponse({
            'status': 'success',
            'staged_id': staged_prod.id,
            'replaced_id': replaced_id,
            'product_code': product_code,
            'next_product_code': generate_next_product_code(),
            'approval_letter_saved': bool(letter_file or keep_letter_name),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return fail(f'Server error: {str(e)}', status=500)


@login_required
def get_staged_product_details(request, staged_id):
    try:
        product = (
            StagedProduct.objects
            .prefetch_related('images', 'variants')
            .get(id=staged_id, seller=request.user, is_submitted=False)
        )

        images = []
        for img in product.images.all():
            try:
                url = img.image.url
            except ValueError:
                continue
            images.append({'id': img.id, 'url': url, 'is_main': img.is_main})

        variants = []
        for v in product.variants.all():
            image_url = None
            if getattr(v, 'image', None):
                try:
                    image_url = v.image.url
                except ValueError:
                    image_url = None
            variants.append({
                'id': v.id,
                'variant_name': v.variant_name,
                'price': str(v.price),
                'stocks': v.stocks,
                'attribute_value': v.variant_attribute or '',   # available sizes, comma-separated
                'image_url': image_url,
            })

        data = {
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'category': product.category_id if product.category else '',
            'category_name': product.category.name if product.category else '',
            'product_code': getattr(product, 'product_code', '') or '',
            'pre_order': product.pre_order,
            'owner_type': product.owner_type,
            'locations': product.meetup_locations_list or '',
            'available_days': product.available_days or '',
            'meetup_time_from': (
                product.preferred_meetup_time_from.strftime('%H:%M')
                if product.preferred_meetup_time_from
                else ''
            ),
            'meetup_time_to': (
                product.preferred_meetup_time_to.strftime('%H:%M')
                if product.preferred_meetup_time_to
                else ''
            ),
            'variants': variants,
            'images': images,
            'size_chart': product.size_chart,
            'payment': product.accepted_payments,
        }
        return JsonResponse(data)
    except StagedProduct.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
@require_POST
def delete_staged_product(request, staged_id):
    deleted, _ = StagedProduct.objects.filter(
        id=staged_id,
        seller=request.user,
        is_submitted=False,
    ).delete()
    if deleted:
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)


def get_attributes(request, category_id):
    """
    Return the 5 most recently used attributes for the given category.
    Ordered by -id so the newest appear first.
    """
    attributes = (
        CategoryAttribute.objects
        .filter(category_id=category_id)
        .order_by('-id')[:5]
        .values('id', 'value', 'attribute_type')
    )
    return JsonResponse({'attributes': list(attributes)})


def _is_cbrgu(seller):
    return getattr(seller, 'user_role', '') in CBRGU_ROLES
 
 
def _shop_products(seller):
    """
    Every product that belongs to this shop.
    CBRGU shop  -> all products listed by CBRGU members (or marked MANAGEMENT).
    Any other   -> the seller's own products.
    """
    if _is_cbrgu(seller):
        return Product.objects.filter(
            Q(owner_type='MANAGEMENT') | Q(seller__user_role__in=CBRGU_ROLES)
        )
    return Product.objects.filter(seller=seller)
 
 
def _shop_seller_reviews(seller, products):
    if _is_cbrgu(seller):
        return SellerReview.objects.filter(
            Q(seller__user_role__in=CBRGU_ROLES) | Q(seller_id__in=products.values('seller_id'))
        )
    return SellerReview.objects.filter(seller=seller)
 
 
def _safe_file_url(f):
    """ImageField -> url, or '' when there is no file."""
    try:
        return f.url if f else ''
    except ValueError:
        return ''
 
 
def _shop_identity(seller):
    """What the shop header shows: kind, name, tagline, logo, 'member since'."""
    role = getattr(seller, 'user_role', '')
    org = getattr(seller, 'org_link', None)
    is_org = getattr(seller, 'is_org_account', False) or role == 'org_officer'
    full = (
        seller.get_full_name()
        or getattr(seller, 'display_name', None)
        or seller.username
        or str(seller.student_no)
    )
 
    if _is_cbrgu(seller):
        # The CBRGU shop is shared, so it never shows one staff member's name or photo.
        return {
            'shop_kind': 'management',
            'shop_name': 'CBRGU',
            'shop_tagline': 'Official shop · all CBRGU listings',
            'shop_description': '',
            'shop_org': None,
            'shop_logo_url': '',
            'member_since': None,
        }
 
    if is_org:
        kind = 'org'
        name = org.name if org else full
        tagline = (org.full_name if org else '') or ''
    else:
        kind, name = 'student', full
        tagline = ' · '.join(p for p in (seller.course, seller.section) if p)
 
    return {
        'shop_kind': kind,
        'shop_name': name,
        'shop_tagline': tagline,
        'shop_description': (org.description if (is_org and org) else '') or '',
        'shop_org': org if is_org else None,
        'shop_logo_url': (_safe_file_url(org.logo) if (is_org and org) else '') or seller.profile_pic_url,
        'member_since': org.date_created if (is_org and org) else seller.date_joined,
    }
 
 
def _rating_block(counts):
    """counts = {5: n, 4: n, ...} -> average, count, star-fill % and the 5..1 bars."""
    total = sum(counts.values())
    avg = (sum(star * n for star, n in counts.items()) / total) if total else 0
    return {
        'count': total,
        'avg': round(avg, 1) if total else 0,
        'pct': round(avg / 5 * 100) if total else 0,
        'dist': [
            {
                'star': s,
                'count': counts.get(s, 0),
                'pct': round(counts.get(s, 0) * 100 / total) if total else 0,
            }
            for s in (5, 4, 3, 2, 1)
        ],
    }
 
 
class StorefrontView(ListView):
    """Seller shop: same filter / sort / card layout as the marketplace, plus shop stats and reviews."""
    model = Product
    template_name = 'UTrade_app/seller/storefront.html'
    context_object_name = 'products'
    paginate_by = 15
 
    def get_seller(self):
        # Cached so the queryset and the context don't each hit the database.
        if not hasattr(self, '_seller'):
            self._seller = get_object_or_404(
                User.objects.select_related('org_link'), pk=self.kwargs['seller_id']
            )
        return self._seller
 
    def get_queryset(self):
        seller = self.get_seller()
        qs = (
            _shop_products(seller)
            .filter(status='Approved')
            .select_related('category', 'seller', 'related_org')
            .prefetch_related('images', 'variants')
        )
 
        query = (self.request.GET.get('q') or '').strip()
        category_id = self.request.GET.get('category')
        sort = self.request.GET.get('sort')
 
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(category__name__icontains=query)
                | Q(product_code__icontains=query)
            )
        if category_id and category_id.isdigit():
            qs = qs.filter(category_id=category_id)
 
        if sort == 'price_low':
            qs = qs.annotate(min_price=Min('variants__price')).order_by('min_price', '-created_at')
        elif sort == 'price_high':
            qs = qs.annotate(min_price=Min('variants__price')).order_by(
                F('min_price').desc(nulls_last=True), '-created_at'
            )
        elif sort == 'popular':
            qs = qs.order_by('-sold', '-created_at')
        else:
            qs = qs.order_by('-created_at')
 
        return qs.distinct()
 
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        seller = self.get_seller()
        request = self.request
        shop_products = _shop_products(seller)
 
        category = request.GET.get('category')
        query = (request.GET.get('q') or '').strip()
 
        context.update(_shop_identity(seller))
        context['shop_seller'] = seller
 
        # ---- Filters (same names as the marketplace so marketplace.js works) ----
        context['categories'] = Category.objects.filter(
            products__in=shop_products.filter(status='Approved')
        ).distinct().order_by('name')
        context['current_category'] = category
        context['current_category_obj'] = (
            Category.objects.filter(pk=category).first() if category and category.isdigit() else None
        )
        context['current_sort'] = request.GET.get('sort') or ''
        context['search_query'] = query
        context['active_filter_count'] = sum(1 for v in (category,) if v)
 
        params = request.GET.copy()
        params.pop('page', None)
        context['querystring'] = params.urlencode()
 
        # ---- Shop stats (the whole shop: for CBRGU that is every CBRGU member) ----
        context['listings_count'] = shop_products.filter(status='Approved').count()
        context['total_sold'] = shop_products.aggregate(s=Sum('sold'))['s'] or 0
 
        seller_reviews_qs = _shop_seller_reviews(seller, shop_products)
        product_reviews_qs = Review.objects.filter(product__in=shop_products)
 
        seller_counts = {
            r['rating']: r['n']
            for r in seller_reviews_qs.values('rating').annotate(n=Count('id')).order_by('rating')
        }
        product_counts = {
            r['rating']: r['n']
            for r in product_reviews_qs.values('rating').annotate(n=Count('id')).order_by('rating')
        }
        context['seller_rating'] = _rating_block(seller_counts)
        context['product_rating'] = _rating_block(product_counts)
 
        # ---- Latest reviews ----
        context['seller_reviews'] = list(
            seller_reviews_qs.select_related('reviewer').order_by('-created_at')[:10]
        )
        context['product_reviews'] = list(
            product_reviews_qs.select_related('user', 'product')
            .prefetch_related('media').order_by('-created_at')[:10]
        )
 
        # ---- Wishlist ----
        if request.user.is_authenticated:
            context['user_wishlist_ids'] = set(
                Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)
            )
        else:
            context['user_wishlist_ids'] = set()
 
        return context