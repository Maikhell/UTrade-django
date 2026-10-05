from decimal import Decimal
import json
from xhtml2pdf import pisa
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import get_template
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import render
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models.functions import TruncDate
from ..utils import send_otp_email, get_seller_owner_type_filter
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)
from xhtml2pdf import pisa

from ..forms import UserProfileForm, UserRegistrationForm
from ..models import (
    MeetupLocation,
    Order,
    OrderItem,
    Organization,
    Product,
    ProductVariant,
    User,
    PreOrderRequest,
)



class UserCreateView(CreateView):
    model = User 
    form_class = UserRegistrationForm
    template_name = 'UTrade_app/accounts/register.html'
    success_url = reverse_lazy('verify_otp') 
    
    def form_valid(self, form):
        user = form.save(commit=False)
        
        chosen_role = self.request.POST.get('user_role', 'student')
        user.user_role = chosen_role if chosen_role in ['student', 'alumni'] else 'student'
        user.is_active = False 
        user.status = 'unverified'
        
        user.save()
        
        self.request.session['pending_user_id'] = user.id
        self.request.session.modified = True
        self.request.session.save() 
        
        try:
            send_otp_email(user)
            messages.info(self.request, f"A verification code has been sent to {user.email}.")
        except Exception as e:
            # Log full error on Railway
            import logging
            logging.getLogger(__name__).exception('OTP email failed for %s', user.email)
            messages.error(
                self.request,
                'Account created, but the verification email could not be sent. '
                'Please try again or contact support.'
            )

        return redirect('/verify-email/')

    def form_invalid(self, form):
        print(f"Form Validation Errors: {form.errors}")
        return super().form_invalid(form)
    
class UserAccountView(TemplateView):
    template_name = 'UTrade_app/accounts/accounts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.is_authenticated:
            context['incoming_orders_count'] = Order.objects.filter(
                items__product_variant__product__seller=self.request.user,
                status='Pending'
            ).distinct().count()
        else:
            context['incoming_orders_count'] = 0
            
        return context
class UserProfileView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'UTrade_app/accounts/profile.html'
    success_url = reverse_lazy('user.profile')
    success_message = "Your profile has been updated successfully!" 
    
    def get_object(self):
        return self.request.user

    def post(self, request, *args, **kwargs):
        """
        Explicitly handle the POST request to ensure manual HTML 
        inputs are captured by the form.
        """
        self.object = self.get_object()
        form = self.get_form()
        
        if form.is_valid():
            return self.form_valid(form)
        else:
            # Debugging: This will show you EXACTLY why it didn't save in your terminal
            print("Form Errors:", form.errors)
            messages.error(self.request, "Validation failed. Please check your inputs.")
            return self.form_invalid(form)

    def form_valid(self, form):
        # Handle profile image upload
        if 'image' in self.request.FILES:
            form.instance.image = self.request.FILES['image']

        # Process Organization string (e.g., "ITS-BSIT")
        org_raw_text = form.cleaned_data.get('organization') 
        
        if org_raw_text:
            parts = [p.strip() for p in org_raw_text.split('-')]
            name_acronym = parts[0]
            course_code = parts[1] if len(parts) > 1 else ""

            org_map = {
                "ITS": "Information Technology Society",
                "CSG": "Central Student Government",
                "ACS": "Alliance of Computer Scientists",
                "HMS": "Hospitality Management Society",
                "LLP": "La Liga Psicologia",
                "LCDCS": "La Ciencia de Crimines Sociedad",
                "LMS-JMA": "Le Manager's Societe - Junior Marketing Association",
                "SHR": "Societas Humana Resource",
                "TES": "Teacher Education Society",
            }

            # get_or_create ensures the Org exists in your PostgreSQL database
            org_obj, created = Organization.objects.get_or_create(
                name=name_acronym,
                defaults={
                    'full_name': org_map.get(name_acronym, name_acronym),
                    'course_code': course_code
                }
            )
            
            # Explicitly link the organization object to the user instance
            form.instance.org_link = org_obj

        # Handle Display Name / Username change
        display_name = form.cleaned_data.get('display_name')
        if display_name:
            if User.objects.filter(username=display_name).exclude(pk=self.request.user.pk).exists():
                messages.error(self.request, "This display name is already taken by another student.")
                return self.form_invalid(form)
            form.instance.username = display_name

        # The super().form_valid(form) call saves the form.instance (the User) 
        # and includes the new org_link relationship.
        return super().form_valid(form)
            


@login_required
def order_delivered(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # Security: make sure this order belongs to the current seller
    if not order.items.filter(product_variant__product__seller=request.user).exists():
        messages.error(request, "You are not allowed to update this order.")
        return redirect('seller.inventory')  # or your dashboard url name

    if request.method == 'POST':
        # Change status to Completed
        order.status = 'Completed'
        order.updated_at = timezone.now()
        order.save(update_fields=['status', 'updated_at'])

        # Optional: you can also set a delivered_at field if you have one
        # order.delivered_at = timezone.now()
        # order.save()

        messages.success(request, f"Order #{order.id} has been marked as Completed.")
        
        # TODO: send notification to buyer here if you have one

    return redirect('seller.inventory')  # change to your actual dashboard url name

class UserProductsView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'UTrade_app/seller/inventory.html'
    context_object_name = 'products'
    paginate_by = 10  # Main product list pagination

    def paginate_queryset_custom(self, queryset, param_name, page_size=5):
        """Helper to safely paginate individual querysets on multi-table pages."""
        paginator = Paginator(queryset, page_size)
        page_number = self.request.GET.get(param_name, 1)
        try:
            return paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            return paginator.page(1)

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()
        seven_days_ago = now - timezone.timedelta(days=7)

        # ==========================================
        # 1. PRE-ORDERS & REPORT FILTERS
        # ==========================================
        seller_preorders = PreOrderRequest.objects.filter(
            seller=user
        ).select_related(
            'buyer',
            'product_variant',
            'product_variant__product',
        ).order_by('-id')

        owner_type = get_seller_owner_type_filter(user)
        if owner_type:
            seller_preorders = seller_preorders.filter(
                product_variant__product__owner_type=owner_type
            )

        incoming_preorders_qs = seller_preorders.filter(
            Q(status__iexact='Pending') | Q(status__iexact='Paid')
        )
        ready_preorders_qs = seller_preorders.filter(
            Q(status__iexact='Accepted')
            | Q(status__iexact='Ready')
            | Q(status__iexact='Ready for Pickup')
        )
        completed_preorders_qs = seller_preorders.filter(
            status__iexact='Completed'
        )

        course_options = (
            seller_preorders
            .exclude(buyer__course__isnull=True)
            .exclude(buyer__course='')
            .values_list('buyer__course', flat=True)
            .distinct()
            .order_by('buyer__course')
        )
        section_options = (
            seller_preorders
            .exclude(buyer__section__isnull=True)
            .exclude(buyer__section='')
            .values_list('buyer__section', flat=True)
            .distinct()
            .order_by('buyer__section')
        )

        # ==========================================
        # 2. PRODUCT BADGE COUNTS & ORDERS QUERYSETS
        # ==========================================
        counts = Product.objects.filter(seller=user).aggregate(
            approved=Count('id', filter=Q(status__iexact='Approved')),
            pending=Count('id', filter=Q(status__iexact='Pending')),
            rejected=Count('id', filter=Q(status__iexact='Rejected'))
        )

        seller_orders = Order.objects.filter(
            items__product_variant__product__seller=user
        ).distinct()

        incoming_orders_qs = seller_orders.filter(
            Q(status__iexact='Pending') | Q(status__iexact='Paid')
        ).order_by('-created_at')

        accepted_orders_qs = seller_orders.filter(
            status__iexact='Accepted'
        ).order_by('-created_at')

        completed_orders_qs = seller_orders.filter(
            status__iexact='Completed'
        ).order_by('-updated_at')

        # Items belonging specifically to this seller from completed orders
        completed_items = OrderItem.objects.filter(
            order__in=completed_orders_qs,
            product_variant__product__seller=user
        )

        # ==========================================
        # 3. STAT CARDS CALCULATIONS
        # ==========================================
        try:
            total_stocks = ProductVariant.objects.filter(
                product__seller=user
            ).aggregate(total=Sum('stock'))['total'] or 0
        except Exception:
            total_stocks = ProductVariant.objects.filter(
                product__seller=user
            ).aggregate(total=Sum('stocks'))['total'] or 0

        total_orders = seller_orders.count()

        total_income = completed_items.aggregate(
            total=Sum(F('price') * F('quantity'))
        )['total'] or Decimal('0.00')

        # ==========================================
        # 4. CHART DATA PREPARATION (JSON SAFE)
        # ==========================================
        # Revenue Over Time (Last 7 Days)
        revenue_daily = (
            completed_items.filter(order__created_at__gte=seven_days_ago)
            .annotate(date=TruncDate('order__created_at'))
            .values('date')
            .annotate(daily_revenue=Sum(F('price') * F('quantity')))
            .order_by('date')
        )
        revenue_labels = [r['date'].strftime('%a') for r in revenue_daily]
        revenue_data = [float(r['daily_revenue'] or 0) for r in revenue_daily]

        # Top Selling Products (Top 5 by units sold)
        top_products_qs = (
            completed_items.values('product_variant__product__name')
            .annotate(total_units=Sum('quantity'))
            .order_by('-total_units')[:5]
        )
        top_products_labels = [p['product_variant__product__name'] or 'Unknown' for p in top_products_qs]
        top_products_data = [p['total_units'] or 0 for p in top_products_qs]

        # Orders Over Time (Last 7 Days)
        orders_daily = (
            seller_orders.filter(created_at__gte=seven_days_ago)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(order_count=Count('id'))
            .order_by('date')
        )
        orders_over_time_labels = [o['date'].strftime('%a') for o in orders_daily]
        orders_over_time_data = [o['order_count'] for o in orders_daily]

        default_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        default_zeros = [0, 0, 0, 0, 0, 0, 0]

        # ==========================================
        # 5. CONTEXT UPDATE
        # ==========================================
        context.update({
            # Product status badges
            'approved_count': counts['approved'] or 0,
            'pending_count': counts['pending'] or 0,
            'rejected_count': counts['rejected'] or 0,

            # Paginated Order Tables (5 items/page for lightweight RAM consumption)
            'incoming_orders': self.paginate_queryset_custom(incoming_orders_qs, 'page_inc', 5),
            'accepted_orders': self.paginate_queryset_custom(accepted_orders_qs, 'page_acc', 5),
            'completed_orders': self.paginate_queryset_custom(completed_orders_qs, 'page_comp', 5),

            # Order Badge Counts
            'incoming_orders_count': incoming_orders_qs.count(),
            'accepted_orders_count': accepted_orders_qs.count(),
            'completed_orders_count': completed_orders_qs.count(),

            # Dashboard Stat Cards
            'total_stocks': total_stocks,
            'total_orders': total_orders,
            'total_income': f"{total_income:,.2f}",

            # Paginated Pre-Orders
            'incoming_preorders': self.paginate_queryset_custom(incoming_preorders_qs, 'page_pre_inc', 5),
            'ready_preorders': self.paginate_queryset_custom(ready_preorders_qs, 'page_pre_ready', 5),
            'completed_preorders': self.paginate_queryset_custom(completed_preorders_qs, 'page_pre_comp', 5),

            # Pre-order Badge Counts
            'incoming_preorder_count': incoming_preorders_qs.count(),
            'ready_preorder_count': ready_preorders_qs.count(),
            'completed_preorder_count': completed_preorders_qs.count(),

            # Filters & Analytics
            'course_options': list(course_options),
            'section_options': list(section_options),
            'owner_type_filter': owner_type,

            # Safe JSON Chart Data
            'revenue_labels_json': json.dumps(revenue_labels if revenue_labels else default_days),
            'revenue_data_json': json.dumps(revenue_data if revenue_data else default_zeros),
            'top_products_labels_json': json.dumps(top_products_labels if top_products_labels else ["No Sales Yet"]),
            'top_products_data_json': json.dumps(top_products_data if top_products_data else [0]),
            'orders_over_time_labels_json': json.dumps(orders_over_time_labels if orders_over_time_labels else default_days),
            'orders_over_time_data_json': json.dumps(orders_over_time_data if orders_over_time_data else default_zeros),
        })

        return context

class ProductUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Product
    fields = ['name', 'description', 'category'] 
    template_name = 'UTrade_app/users/account/edit_product.html'
    success_url = reverse_lazy('seller_inventory')
    success_message = "Product updated successfully!"

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user)

    def form_valid(self, form):
        form.instance.status = 'Pending'
        
        form.instance.seller = self.request.user
        
        messages.info(self.request, "Product changes saved! It is now pending admin review before going live again.")
        
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from ..models import MeetupLocation # Local import to avoid circular issues
        context['locations'] = MeetupLocation.objects.filter(is_active=True)
        return context

class ProductDeleteView(LoginRequiredMixin, DeleteView):
    model = Product
    success_url = reverse_lazy('seller_inventory')

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user)

    def delete(self, request, *args, **kwargs):
        product = self.get_object()
        messages.success(request, f"Listing for '{product.name}' was successfully removed.")
        return super().delete(request, *args, **kwargs)  
@login_required
def update_terms_agreement(request):
    if request.method == "POST":
        user = request.user
        user.has_agreed_to_terms = True
        user.save()
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error"}, status=400)

@login_required
def update_cor(request):
    if request.method == 'POST':
        user = request.user
        cor_file = request.FILES.get('cor_file')
        required_fields = [user.first_name, user.last_name, user.student_no, user.course, user.section]
        if not all(required_fields):
            messages.error(request, "Please complete your Profile (Name, Student No, Course, and Section) before uploading your COR.")
            return redirect('user.profile') # Adjust name to your edit profile URL

        if cor_file:
            user.cor_file = cor_file
            user.status = 'Pending' 
            user.save()
            if user.status == 'unverified':
                messages.success(request, "COR submitted! Admin will review your account soon.")
            else:
                messages.success(request, "Your COR has been updated and is now pending for re-verification.")
        else:
            messages.error(request, "Please select a file to upload.")

    return redirect('user.account')
@login_required
def register_officer(request):
    if request.method == 'POST':
        user = request.user
        
        organization = request.POST.get('organization')
        position = request.POST.get('position')
        officer_id_image = request.FILES.get('officer_id_image')

        if organization and position and officer_id_image:
            user.organization = organization
            user.position = position
            user.officer_id_image = officer_id_image
            user.officer_status = 'pending'
            user.save()

            messages.success(request, "Officer application submitted! Please wait for admin verification.")
        else:
            messages.error(request, "Please fill in all fields and upload your ID.")
            
        return redirect('user.profile')
    
    return redirect('user.account')

def _money(value):
    """Always return a plain string PDF engines can render (no ₱ glyph)."""
    if value is None:
        value = Decimal('0')
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f'{value.quantize(Decimal("0.01"))}'


@login_required
def seller_sales_report(request):
    """
    PDF sales report for the logged-in seller.
    Optional query: ?period=7d|30d|all  (default 30d)
    """
    seller = request.user
    period = request.GET.get('period', '30d')
    now = timezone.now()

    if period == '7d':
        since = now - timezone.timedelta(days=7)
        period_label = 'Last 7 days'
    elif period == 'all':
        since = None
        period_label = 'All time'
    else:
        since = now - timezone.timedelta(days=30)
        period_label = 'Last 30 days'
        period = '30d'

    seller_orders = Order.objects.filter(
        items__product_variant__product__seller=seller
    ).distinct()

    if since:
        seller_orders = seller_orders.filter(created_at__gte=since)

    completed = (
        seller_orders.filter(status__iexact='Completed')
        .select_related('user')
        .order_by('-updated_at')
    )

    total_orders = seller_orders.count()
    completed_orders_count = completed.count()

    total_revenue = completed.aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    total_revenue = Decimal(str(total_revenue))

    item_qs = OrderItem.objects.filter(
        order__in=completed,
        product_variant__product__seller=seller,
    )
    total_units_sold = item_qs.aggregate(s=Sum('quantity'))['s'] or 0

    # 3% only for organization-type sellers; personal sellers = 0
    role = (getattr(seller, 'user_role', '') or '').lower()
    is_org = role in ('organization', 'org', 'alumni_assoc') or getattr(seller, 'is_officer', False)
    FEE_RATE = Decimal('0.03') if is_org else Decimal('0.00')

    platform_fee = (total_revenue * FEE_RATE).quantize(Decimal('0.01'))
    net_profit = (total_revenue - platform_fee).quantize(Decimal('0.01'))

    avg_order_value = (
        (total_revenue / completed_orders_count).quantize(Decimal('0.01'))
        if completed_orders_count
        else Decimal('0')
    )

    active_products = Product.objects.filter(
        seller=seller, status__iexact='Approved'
    ).count()

    top_raw = (
        item_qs.values('product_variant__product__name')
        .annotate(
            units=Sum('quantity'),
            revenue=Sum(F('price') * F('quantity')),
        )
        .order_by('-units')[:10]
    )
    top_products = [
        {
            'name': r['product_variant__product__name'] or 'Unknown',
            'units': r['units'] or 0,
            'revenue': _money(r['revenue']),
        }
        for r in top_raw
    ]

    # Format order amounts for the table (avoids odd Decimal rendering)
    completed_list = list(completed[:100])
    for o in completed_list:
        o.total_amount_display = _money(o.total_amount)

    context = {
        'seller': seller,
        'period_label': period_label,
        'generated_at': now,
        'total_orders': total_orders,
        'completed_orders_count': completed_orders_count,
        'total_units_sold': total_units_sold,
        'total_revenue': _money(total_revenue),
        'platform_fee': _money(platform_fee),
        'net_profit': _money(net_profit),
        'avg_order_value': _money(avg_order_value),
        'active_products': active_products,
        'completed_orders': completed_list,
        'top_products': top_products,
        'fee_rate_label': '3%' if is_org else '0% (personal seller)',
    }

    template = get_template('UTrade_app/reports/seller_sales_report.html')
    html = template.render(context, request=request)

    response = HttpResponse(content_type='application/pdf')
    filename = f"UTrade_Sales_{seller.username}_{period}_{now.strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    pisa_status = pisa.CreatePDF(html, dest=response, encoding='utf-8')
    if pisa_status.err:
        return HttpResponse('Error generating PDF report.', status=500)
    return response

def _get_managed_preorder(request, preorder_id):
    """Fetch pre-order only if seller owns it AND owner_type matches role."""
    qs = PreOrderRequest.objects.filter(
        id=preorder_id,
        seller=request.user,
    ).select_related('product_variant__product')

    owner_type = get_seller_owner_type_filter(request.user)
    if owner_type:
        qs = qs.filter(product_variant__product__owner_type=owner_type)

    return get_object_or_404(qs)
def preorder_mark_ready(request, preorder_id):
    po = _get_managed_preorder(request, preorder_id)
    po.status = 'Ready'
    po.save(update_fields=['status'])
    messages.success(request, f'Pre-order #{po.id} marked ready for pickup.')
    return redirect('seller_inventory')

def preorder_mark_completed(request, preorder_id):
    po = _get_managed_preorder(request, preorder_id)
    po.status = 'Completed'
    po.save(update_fields=['status'])
    messages.success(request, f'Pre-order #{po.id} completed.')
    return redirect('seller_inventory')

def seller_preorder_report(request):
    seller = request.user
    scope = request.GET.get('scope', 'all')
    course = (request.GET.get('course') or '').strip()
    section = (request.GET.get('section') or '').strip()
    now = timezone.now()

    qs = PreOrderRequest.objects.filter(seller=seller).select_related(
        'buyer', 'product_variant', 'product_variant__product'
    )

    owner_type = get_seller_owner_type_filter(seller)
    if owner_type:
        qs = qs.filter(product_variant__product__owner_type=owner_type)

    if scope == 'completed':
        qs = qs.filter(status__iexact='Completed')
        scope_label = 'Completed Pre-Orders'
    else:
        scope_label = 'All Pre-Orders'

    if course:
        qs = qs.filter(buyer__course__iexact=course)
    if section:
        qs = qs.filter(buyer__section__iexact=section)

    qs = qs.order_by('-id')

    context = {
        'seller': seller,
        'scope_label': scope_label,
        'course': course or 'All',
        'section': section or 'All',
        'owner_type': owner_type or 'ALL',
        'generated_at': now,
        'preorders': qs[:200],
        'total_count': qs.count(),
        'total_qty': qs.aggregate(s=Sum('quantity'))['s'] or 0,
    }

    template = get_template('UTrade_app/reports/seller_preorder_report.html')
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    filename = f"UTrade_PreOrders_{seller.username}_{now.strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    pisa_status = pisa.CreatePDF(html, dest=response, encoding='utf-8')
    if pisa_status.err:
        return HttpResponse('Error generating PDF report.', status=500)
    return response


@login_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    name = product.name
    product.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': f'{name} removed.'})
    messages.success(request, f'“{name}” was removed.')
    return redirect('seller_inventory')

@login_required
@require_POST
def variant_delete(request, pk):
    variant = get_object_or_404(
        ProductVariant,
        pk=pk,
        product__seller=request.user,
    )
    product = variant.product
    variant.delete()
    # Optional: force re-review if product was live
    if product.status == 'Approved':
        product.status = 'Pending'
        product.save(update_fields=['status'])
        notice = 'Variant removed. Product returned to Pending for re-approval.'
    else:
        notice = 'Variant removed.'

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': notice})
    messages.success(request, notice)
    return redirect('seller_inventory')

@login_required
@require_POST
def variant_create(request, product_id):
    product = get_object_or_404(
        Product,
        pk=product_id,
        seller=request.user
    )

    variant_name = (request.POST.get('variant_name') or '').strip()
    attribute_value = (request.POST.get('attribute_value') or '').strip()
    price = request.POST.get('price')
    stocks = request.POST.get('stocks')

    if not variant_name:
        messages.error(request, "Variant name is required.")
        return redirect('seller_inventory')

    try:
        price = Decimal(price)
        stocks = int(stocks)
    except (TypeError, ValueError, ArithmeticError):
        messages.error(request, "Please enter a valid price and stock quantity.")
        return redirect('seller_inventory')

    if price < 0 or stocks < 0:
        messages.error(request, "Price and stock cannot be negative.")
        return redirect('seller_inventory')

    ProductVariant.objects.create(
        product=product,
        variant_name=variant_name,
        attribute_value=attribute_value,
        price=price,
        stocks=stocks,
    )

    # Any change to a live product requires re-approval.
    if product.status == 'Approved':
        product.status = 'Pending'
        product.save(update_fields=['status'])
        message = (
            f"Variant added to '{product.name}'. "
            "The product has been returned to Pending for re-approval."
        )
    else:
        message = f"Variant added to '{product.name}'."

    messages.success(request, message)
    return redirect('seller_inventory')