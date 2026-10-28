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
import re
from ..utils import is_allowed_email
from django import forms
import logging
logger = logging.getLogger(__name__)
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
from ..course_utils import COURSE_CHOICES
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
    ChatMessage,
)

REVERIFY_FIELDS = (
    ('first_name', 'First name'),
    ('last_name', 'Last name'),
    ('suffix', 'Suffix'),
    ('student_no', 'Student number'),
    ('email', 'Email'),
    ('course', 'Course'),
    ('section', 'Section'),
)
ORG_LOCKED_FIELDS = ('first_name', 'last_name', 'student_no')
def _norm(field, value):
    value = (value or '').strip()
    return value.lower() if field == 'email' else value

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
    
    def clean_student_no(self):
        student_no = self.cleaned_data.get('student_no', '').strip()
        if not re.fullmatch(r'\d{9}', student_no):
            raise forms.ValidationError("Student number must be exactly 9 digits.")
        return student_no
    
    def form_invalid(self, form):
        print(f"Form Validation Errors: {form.errors}")
        return super().form_invalid(form)

class UserAccountView(TemplateView):
    template_name = 'UTrade_app/accounts/accounts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['incoming_orders_count'] = 0
        context['unread_messages_count'] = 0
        context['mgmt_pending_count'] = 0
        context['org_pending_count'] = 0

        if not user.is_authenticated:
            return context

        context['incoming_orders_count'] = (
            Order.objects.filter(
                items__product_variant__product__seller=user,
                status__iexact='Pending',
            )
            .distinct()
            .count()
        )

        # Unread chats: messages in your conversations not sent by you
        context['unread_messages_count'] = ChatMessage.objects.filter(
            Q(conversation__buyer=user) | Q(conversation__seller=user),
            is_read=False,
        ).exclude(user=user).count()

        if user.user_role == 'management':
            pending_products = Product.objects.filter(status__iexact='Pending').count()
            pending_pre = PreOrderRequest.objects.filter(
                status__iexact='PENDING',
                product_variant__product__owner_type='MANAGEMENT',
            ).count()
            context['mgmt_pending_count'] = pending_products + pending_pre

        if user.is_officer or user.user_role == 'org_officer':
            org = getattr(user, 'org_link', None)
            if org:
                context['org_pending_count'] = PreOrderRequest.objects.filter(
                    status__iexact='PENDING',
                    product_variant__product__related_org=org,
                ).count()
            else:
                context['org_pending_count'] = context['incoming_orders_count']

        return context
class UserProfileView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'UTrade_app/accounts/profile.html'
    success_url = reverse_lazy('user.profile')
    success_message = "Your profile has been updated successfully!"
 
    def get_object(self, queryset=None):
        return self.request.user
 
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['org'] = user.org_link
        context['course_choices'] = COURSE_CHOICES          # <- fills the dropdown
        context['manager'] = user.active_manager             # org accounts
        context['managed_accounts'] = (
            user.managed_accounts if user.user_role == 'student' else []
        )
        return context
 
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        user = self.request.user
        if self.request.method == 'POST' and user.is_org_account:
            data = self.request.POST.copy()
            for f in ORG_LOCKED_FIELDS:
                data[f] = getattr(user, f) or ''
            kwargs['data'] = data
        return kwargs
 
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        user = self.object
        # Snapshot BEFORE the form validates (validation mutates the instance).
        self._original = {f: (getattr(user, f) or '') for f, _ in REVERIFY_FIELDS}
        self._was_verified = (user.status or '').lower() == 'verified'
 
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        messages.error(request, "Validation failed. Please check your inputs.")
        return self.form_invalid(form)
 
    def _reject(self, text):
        # Nothing has been saved yet, so just go back to the page.
        messages.error(self.request, text)
        return redirect('user.profile')
 
    def form_valid(self, form):
        user = form.instance
        post = self.request.POST
        role = user.user_role
        is_org = user.is_org_account
        is_student = role == 'student'
 
        if 'image' in self.request.FILES:
            user.image = self.request.FILES['image']
 
        if not is_org:
            user.suffix = post.get('suffix', '').strip() or None
            user.gender = post.get('gender', '') or None
 
        # ---- Email (not part of UserProfileForm, so handled here) ----
        email = post.get('email', '').strip().lower()
        if not email:
            return self._reject("Email is required.")
        if email != self._original['email'].strip().lower():
            if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                return self._reject("That email is already registered.")
            if is_student and not is_allowed_email(email):
                return self._reject("Use a Gmail or official @cvsu.edu.ph email address.")
        user.email = email
 
        # ---- Student-style fields ----
        if not is_org and role not in ('management', 'campus_admin'):
            user.phone_number = post.get('phone_number', '').strip() or None
            user.course = post.get('course', '').strip() or None
            user.section = post.get('section', '').strip() or None
            if not user.phone_number:
                return self._reject("Contact number is required.")
            if not user.course:
                return self._reject("Course is required.")
            if not user.section:
                return self._reject("Section is required.")
 
        if is_student and not re.fullmatch(r'\d{9}', user.student_no or ''):
            return self._reject("Student number must be exactly 9 digits.")
 
        # ---- Re-verification: verified STUDENT accounts only ----
        if is_student and self._was_verified:
            current = {f: getattr(user, f) for f, _ in REVERIFY_FIELDS}
            changed = [
                label for f, label in REVERIFY_FIELDS
                if _norm(f, current[f]) != _norm(f, self._original[f])
            ]
            if changed:
                user.status = 'pending'
                messages.info(
                    self.request,
                    "Your account is now Pending until it is verified again."
                )
 
        # ---- Organization details (org accounts / alumni association) ----
        if is_org or role == 'alumni_assoc':
            org = user.org_link
            org_name = post.get('org_name', '').strip()
            org_full_name = post.get('org_full_name', '').strip()
            org_description = post.get('org_description', '').strip()
 
            if org:
                if org_name and org_name != org.name:
                    if Organization.objects.filter(name=org_name).exclude(pk=org.pk).exists():
                        return self._reject("Another organization already uses that name.")
                    org.name = org_name
                    user.organization = org_name
                if org_full_name:
                    org.full_name = org_full_name
                org.description = org_description
                org.save()
            elif org_name and role == 'alumni_assoc':
                org = Organization.objects.create(
                    name=org_name,
                    full_name=org_full_name or org_name,
                    description=org_description,
                )
                user.org_link = org
                user.organization = org_name
 
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

def get_seller_owner_type_filter(user):
    """Return owner_type filter for org sellers, or None for management."""
    if getattr(user, 'user_role', None) == 'management':
        return None
    return getattr(user, 'organization', None) or None
class UserProductsView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'UTrade_app/seller/inventory.html'  # change if your path differs
    context_object_name = 'products'
    paginate_by = 10

    def get_queryset(self):
        return (
            Product.objects
            .filter(seller=self.request.user)
            .order_by('-created_at')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()
        seven_days_ago = now - timezone.timedelta(days=7)

        default_days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        default_zeros = [0, 0, 0, 0, 0, 0, 0]

        # ---------- Pre-orders ----------
        seller_preorders = (
            PreOrderRequest.objects
            .filter(seller=user)
            .select_related('buyer', 'product_variant', 'product_variant__product')
            .order_by('-id')
        )
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
            | Q(status__iexact='ACCEPTED')
            | Q(status__iexact='READY')
        )
        completed_preorders_qs = seller_preorders.filter(
            status__iexact='Completed'
        )

        preorders_daily = (
            seller_preorders
            .filter(created_at__gte=seven_days_ago)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(order_count=Count('id'))
            .order_by('date')
        )
        preorders_over_time_labels = [
            o['date'].strftime('%a') for o in preorders_daily if o['date']
        ]
        preorders_over_time_data = [o['order_count'] for o in preorders_daily]

        # ---------- Orders ----------
        seller_orders = (
            Order.objects
            .filter(items__product_variant__product__seller=user)
            .distinct()
        )
        incoming_orders_qs = seller_orders.filter(
            Q(status__iexact='Pending') | Q(status__iexact='Paid')
        )
        accepted_orders_qs = seller_orders.filter(status__iexact='Accepted')
        completed_orders_qs = seller_orders.filter(status__iexact='Completed')

        completed_items = OrderItem.objects.filter(
            order__in=completed_orders_qs,
            product_variant__product__seller=user,
        )

        # ---------- Stat cards ----------
        try:
            total_stocks = (
                ProductVariant.objects
                .filter(product__seller=user)
                .aggregate(total=Sum('stocks'))['total']
            ) or 0
        except Exception:
            total_stocks = (
                ProductVariant.objects
                .filter(product__seller=user)
                .aggregate(total=Sum('stock'))['total']
            ) or 0

        total_orders = seller_orders.count()
        total_preorders = seller_preorders.count()
        total_income = completed_items.aggregate(
            total=Sum(F('price') * F('quantity'))
        )['total'] or Decimal('0.00')

        # ---------- Chart data ----------
        revenue_daily = (
            completed_items
            .filter(order__created_at__gte=seven_days_ago)
            .annotate(date=TruncDate('order__created_at'))
            .values('date')
            .annotate(daily_revenue=Sum(F('price') * F('quantity')))
            .order_by('date')
        )
        revenue_labels = [r['date'].strftime('%a') for r in revenue_daily if r['date']]
        revenue_data = [float(r['daily_revenue'] or 0) for r in revenue_daily]

        top_products_qs = (
            completed_items
            .values('product_variant__product__name')
            .annotate(total_units=Sum('quantity'))
            .order_by('-total_units')[:5]
        )
        top_products_labels = [
            p['product_variant__product__name'] or 'Unknown' for p in top_products_qs
        ]
        top_products_data = [p['total_units'] or 0 for p in top_products_qs]

        orders_daily = (
            seller_orders
            .filter(created_at__gte=seven_days_ago)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(order_count=Count('id'))
            .order_by('date')
        )
        orders_over_time_labels = [
            o['date'].strftime('%a') for o in orders_daily if o['date']
        ]
        orders_over_time_data = [o['order_count'] for o in orders_daily]

        context.update({
            'total_stocks': total_stocks,
            'total_orders': total_orders,
            'total_preorders': total_preorders,
            'total_income': f'{total_income:,.2f}',

            'incoming_orders_count': incoming_orders_qs.count(),
            'accepted_orders_count': accepted_orders_qs.count(),
            'completed_orders_count': completed_orders_qs.count(),

            'incoming_preorder_count': incoming_preorders_qs.count(),
            'ready_preorder_count': ready_preorders_qs.count(),
            'completed_preorder_count': completed_preorders_qs.count(),

            'revenue_labels_json': json.dumps(revenue_labels or default_days),
            'revenue_data_json': json.dumps(revenue_data or default_zeros),
            'top_products_labels_json': json.dumps(
                top_products_labels or ['No Sales Yet']
            ),
            'top_products_data_json': json.dumps(top_products_data or [0]),
            'orders_over_time_labels_json': json.dumps(
                orders_over_time_labels or default_days
            ),
            'orders_over_time_data_json': json.dumps(
                orders_over_time_data or default_zeros
            ),
            'preorders_over_time_labels_json': json.dumps(
                preorders_over_time_labels or default_days
            ),
            'preorders_over_time_data_json': json.dumps(
                preorders_over_time_data or default_zeros
            ),
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