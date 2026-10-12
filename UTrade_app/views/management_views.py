import json
import uuid
from datetime import timedelta
from itertools import chain
from django.core.mail import send_mail
from django.conf import settings
import logging
logger = logging.getLogger(__name__)
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template, render_to_string
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import UpdateView
from django.db import transaction
from decimal import Decimal
from django.db.models import Subquery, OuterRef, Value, DecimalField
from django.db.models.functions import Coalesce
from django.db.models import Prefetch
from django.utils.dateparse import parse_date

from xhtml2pdf import pisa

from ..forms import ProductForm
from ..models import (
    CartItem,
    Category,
    CategoryAttribute,
    ChatMessage,
    Conversation,
    MeetupLocation,
    Order,
    OrderItem,
    PreOrderRequest,
    Product,
    ProductVariant,
    ProhibitedWord,
    Review,
    Organization,
    SystemLog,
    User,
    UserReport,
    PlatformFeeLine,
    OrganizationPlatformLedger,
    PlatformFeeRemittance
    
)
from ..utils import log_action

class ManagementPanelView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        search_query = request.GET.get('search', '')
        status_filter = request.GET.get('status_filter', '')
        pre_order_filter = request.GET.get('pre_order', '')
        sort_param = request.GET.get('sort', '-date_joined')

        users = User.objects.all().exclude(id=request.user.id)

        if search_query:
            users = users.filter(
                Q(username__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
                | Q(student_no__icontains=search_query)
            )

        if status_filter:
            users = users.filter(status=status_filter)

        users = users.order_by(sort_param)[:50]

        # Live inventory (Approved products)
        approved_products = (
            Product.objects.filter(status='Approved')
            .select_related('seller', 'category')
            .prefetch_related('variants', 'images')
            .order_by('-created_at')
        )

        if search_query:
            approved_products = approved_products.filter(
                Q(name__icontains=search_query)
                | Q(seller__first_name__icontains=search_query)
                | Q(seller__last_name__icontains=search_query)
                | Q(variants__price__icontains=search_query)
            ).distinct()

        if pre_order_filter:
            is_pre = pre_order_filter == 'True'
            approved_products = approved_products.filter(pre_order=is_pre)

        page_number = request.GET.get('page', 1)
        paginator = Paginator(approved_products, 15)
        page_obj = paginator.get_page(page_number)

        reported_items = (
            UserReport.objects.select_related(
                'reporter',
                'reported_user',
                'conversation',
                'conversation__product',
                'conversation__buyer',
                'conversation__seller',
            )
            .order_by('-created_at')[:50]
        )

        pending_products = (
            Product.objects.filter(status='Pending')
            .select_related('seller', 'category')
            .prefetch_related('variants', 'images')
            .order_by('-created_at')[:50]
        )

        incoming_preorders = (
            PreOrderRequest.objects.filter(seller__user_role='management')
            .select_related('buyer', 'product_variant__product')
            .order_by('-created_at')[:50]
        )

        completed_orders = Order.objects.filter(status='Completed')[:50]

        # ---------- Platform fees (3% org cycles) ----------
        fee_ledgers = (
            OrganizationPlatformLedger.objects.filter(status__in=['OPEN', 'DUE'])
            .select_related('organization')
            .order_by('cycle_due')
        )
        fee_warnings = [L for L in fee_ledgers if L.is_warning or L.is_overdue]
        organizations = Organization.objects.all().order_by('name')
        
        
        context = {
            'org_name': 'UTrade Global Management',
            'target_course': 'campus',
            'org': request.user.org_link,
            'users': users,
            'verified_count': User.objects.filter(status='verified').count(),
            # Inventory
            'approved_items': page_obj,
            'approved_count': paginator.count,
            'active_products_count': paginator.count,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            # Pending
            'pending_products': pending_products,
            'pending_products_count': Product.objects.filter(status='Pending').count(),
            # Reports / logs / orders
            'reported_items': reported_items,
            'logs': SystemLog.objects.all()[:30],
            'incoming_orders': incoming_preorders,
            'completed_orders': completed_orders,
            # Platform fees
            'fee_ledgers': fee_ledgers,
            'fee_warnings': fee_warnings,
            'organizations': organizations,
        }

        return render(request, 'UTrade_app/management/management_panel/dashboard.html', context)

class ProductUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'UTrade_app/products/edit_product.html'

    def test_func(self):
        return self.get_object().seller_id == self.request.user.id

    def form_valid(self, form):
        product = form.save(commit=False)
        product.status = 'Pending'  # force re-review after edit
        product.save()

        # Optional: update variants from POST JSON
        variants_raw = self.request.POST.get('variants')
        if variants_raw:
            import json
            try:
                variants = json.loads(variants_raw)
            except json.JSONDecodeError:
                variants = []
            for v in variants:
                vid = v.get('id')
                if vid:
                    ProductVariant.objects.filter(
                        id=vid, product=product
                    ).update(
                        variant_name=v.get('name', ''),
                        attribute_value=v.get('attribute', ''),
                        price=v.get('price') or 0,
                        stocks=v.get('stock') or 0,
                        condition=v.get('condition', 'Brand New'),
                        flaws_description=v.get('flaws', ''),
                    )
                else:
                    ProductVariant.objects.create(
                        product=product,
                        variant_name=v.get('name', ''),
                        attribute_value=v.get('attribute', ''),
                        price=v.get('price') or 0,
                        stocks=v.get('stock') or 0,
                        condition=v.get('condition', 'Brand New'),
                        flaws_description=v.get('flaws', ''),
                    )

        messages.warning(
            self.request,
            f'“{product.name}” was updated and sent back to Management for approval. '
            f'It is hidden from the marketplace until approved again.'
        )
        return redirect('seller_inventory')
def update_status(request, type, id):
    new_status = request.GET.get('status')
    
    
    if type == 'product':
        item = get_object_or_404(Product, id=id)
    elif type == 'user':
        item = get_object_or_404(User, id=id)
    
    item.status = new_status
    item.save()

    item_name = getattr(item, 'name', str(item))
    log_action(
        user=request.user,
        action=f"Status Changed to {new_status}",
        item_type=type.capitalize(),
        item_name=item_name,
        details=f"Admin updated {type} ID:{id} status to {new_status}"
    )

    messages.success(request, f"{type.capitalize()} updated successfully!")
    return redirect('active_listings')


def product_details(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related('seller', 'category')
        .prefetch_related('variants', 'images'),
        id=product_id
    )

    # ---------------------------------------
    # MEETUP AVAILABILITY
    # ---------------------------------------

    # Location
    meetup_location = (product.meetup_location_text or '').strip()

    # Available days
    raw_days = (product.available_days or '').strip()

    available_days_list = []

    if raw_days:
        available_days_list = [
            day.strip()
            for day in raw_days.split(',')
            if day.strip()
        ]

    # Time
    meetup_time_from = product.preferred_meetup_time_from
    meetup_time_to = product.preferred_meetup_time_to

    return render(
        request,
        'UTrade_app/management/product_view.html',
        {
            'product': product,

            # Meetup information
            'meetup_location': meetup_location,
            'available_days_list': available_days_list,
            'meetup_time_from': meetup_time_from,
            'meetup_time_to': meetup_time_to,
        }
    )


def generate_report_pdf(request):
    report_type = request.GET.get('report_type')
    today = timezone.now()
    
    # 1. Data Selection Logic
    data = []
    title = ""
    
    if report_type == 'live_products':
        title = "Live Inventory Report (On-Hand)"
        data = Product.objects.filter(status='Approved', pre_order=False)
    elif report_type == 'pre_orders':
        title = "Management Pre-Order Report"
        data = Product.objects.filter(status='Approved', pre_order=True)
    elif report_type == 'all_products':
        title = "Complete Product Masterlist"
        data = Product.objects.all()
    elif report_type == 'user_logs':
        title = "System Activity Logs"
        data = SystemLog.objects.all()[:100]
    elif report_type == 'completed_preorders':
        title = "Completed Pre-Order Transactions"
        data = Order.objects.filter(
            status='Completed', 
            product__pre_order=True
        ).order_by('-updated_at')
    template_path = 'UTrade_app/management/report_pdf.html'
    context = {
        'title': title,
        'data': data,
        'report_type': report_type,
        'today': today,
        'generated_by': request.user.get_full_name() or request.user.username
    }
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_{today.strftime("%Y%m%d")}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(
    html, 
    dest=response,
    encoding='utf-8' 
)
    
    if pisa_status.err:
       return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response

def is_management(user):
    return user.is_authenticated and user.user_role == 'management'

@login_required
@user_passes_test(is_management)
def security_admin(request):
    context = {
        'prohibited_words': ProhibitedWord.objects.all().order_by('-created_at'),
        'categories': Category.objects.all().order_by('name'),
        'meetups': MeetupLocation.objects.all().order_by('name'),  
    }
    # Move the template to a management folder if preferred
    return render(request, 'UTrade_app/management/security.html', context)

@require_POST
@user_passes_test(is_management)
def add_bad_word(request):
    word_text = request.POST.get('word', '').strip().lower()
    if word_text:
        word_obj, created = ProhibitedWord.objects.get_or_create(word=word_text)
        if created:
            return JsonResponse({'status': 'success', 'word': word_obj.word, 'id': word_obj.id})
        return JsonResponse({'status': 'error', 'message': 'Word already exists.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid input.'})

@require_POST
@user_passes_test(is_management)
def delete_bad_word(request, word_id):
    ProhibitedWord.objects.filter(id=word_id).delete()
    return JsonResponse({'status': 'success'})

@require_POST
@user_passes_test(is_management)
def add_category(request):
    if request.method == 'POST':
        try:
            # Parse the JSON data from the request body
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            attributes = data.get('attributes', []) # This is our list of {type, value}

            if not name:
                return JsonResponse({'status': 'error', 'message': 'Name cannot be empty.'})

            # 1. Create the Category
            category, created = Category.objects.get_or_create(name=name)
            
            if not created:
                return JsonResponse({'status': 'error', 'message': 'Category already exists.'})

            # 2. Loop through and create the linked Attributes
            for attr in attributes:
                attr_value = attr.get('value', '').strip()
                attr_type = attr.get('type', 'size')
                
                if attr_value:
                    CategoryAttribute.objects.get_or_create(
                        category=category,
                        value=attr_value,
                        attribute_type=attr_type,
                        defaults={
                            'is_custom': False, # Mark as official admin attribute
                            'created_by': request.user
                        }
                    )

            return JsonResponse({
                'status': 'success', 
                'name': category.name, 
                'id': category.id
            })

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid data format.'})
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

@require_POST
@user_passes_test(is_management)
def delete_category(request, cat_id):
    Category.objects.filter(id=cat_id).delete()
    return JsonResponse({'status': 'success'})

@require_POST
@user_passes_test(is_management)
def add_meetup(request):
    location_name = request.POST.get('location', '').strip() 
    if location_name:
        if MeetupLocation.objects.filter(name__iexact=location_name).exists():
            return JsonResponse({'status': 'error', 'message': 'Location already exists.'}, status=400)
        location = MeetupLocation.objects.create(name=location_name, added_by=request.user)
        return JsonResponse({'status': 'success', 'location': location.name, 'id': location.id})
    return JsonResponse({'status': 'error', 'message': 'Location name is required.'}, status=400)

@require_POST
@user_passes_test(is_management)
def delete_meetup(request, loc_id):
    MeetupLocation.objects.filter(id=loc_id).delete()
    return JsonResponse({'status': 'success'})

def get_prohibited_words(request):
    words = list(ProhibitedWord.objects.values_list('word', flat=True))
    return JsonResponse({'prohibited_words': words})

def is_management(user):
    return user.is_authenticated and user.user_role == 'management'


def _notify_seller(admin_user, product, message_text):
    """Open/reuse conversation as admin (buyer side) with seller, about this product."""
    conversation, _ = Conversation.objects.get_or_create(
        product=product,
        buyer=admin_user,   # management acts as initiator
        seller=product.seller,
    )
    ChatMessage.objects.create(
        conversation=conversation,
        user=admin_user,
        content=message_text,
        is_read=False,
    )
    return conversation


@login_required
@user_passes_test(is_management)
@require_POST
def management_reject_product(request, product_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

    reason = (data.get('reason') or '').strip()
    if not reason:
        return JsonResponse({'success': False, 'message': 'Reason required'}, status=400)

    product = get_object_or_404(Product, id=product_id)
    product.status = 'Rejected'
    product.save(update_fields=['status'])

    msg = (
        f"🚨 SYSTEM (Management): Your product \"{product.name}\" was rejected.\n"
        f"Reason: {reason}\n"
        f"You may edit and resubmit it for review."
    )
    _notify_seller(request.user, product, msg)

    log_action(
        user=request.user,
        action="Product Rejected",
        item_type="Product",
        item_name=product.name,
        details=f"Rejected ID:{product.id}. Reason: {reason}",
    )

    return JsonResponse({'success': True, 'message': 'Product rejected and seller notified.'})


@login_required
@user_passes_test(is_management)
@require_POST
def management_unlist_product(request, product_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

    reason = (data.get('reason') or '').strip()
    if not reason:
        return JsonResponse({'success': False, 'message': 'Reason required'}, status=400)

    product = get_object_or_404(Product, id=product_id, status='Approved')
    product.status = 'Unlisted'  # or 'Rejected' / 'Pending' — match your STATUS choices
    product.save(update_fields=['status'])

    msg = (
        f"🚨 SYSTEM (Management): Your product \"{product.name}\" was unlisted from the marketplace.\n"
        f"Reason: {reason}\n"
        f"Contact management if you have questions."
    )
    _notify_seller(request.user, product, msg)

    log_action(
        user=request.user,
        action="Product Unlisted",
        item_type="Product",
        item_name=product.name,
        details=f"Unlisted ID:{product.id}. Reason: {reason}",
    )

    return JsonResponse({'success': True, 'message': 'Product unlisted and seller notified.'})

def seller_sales_chart_data(request):
    """JSON for Chart.js — completed orders only."""
    user = request.user
    days = int(request.GET.get('days', 30))
    since = timezone.now() - timedelta(days=days)

    # Prefer OrderItem path if multi-seller cart
    qs = (
        OrderItem.objects.filter(
            product_variant__product__seller=user,
            order__status__iexact='Completed',
            order__updated_at__gte=since,  # or created_at / completed_at
        )
        .annotate(day=TruncDate('order__updated_at'))
        .values('day')
        .annotate(
            revenue=Sum(F('price') * F('quantity')),
            units=Sum('quantity'),
            orders=Count('order_id', distinct=True),
        )
        .order_by('day')
    )

    labels = [r['day'].strftime('%b %d') for r in qs if r['day']]
    revenue = [float(r['revenue'] or 0) for r in qs]
    units = [int(r['units'] or 0) for r in qs]

    return JsonResponse({
        'labels': labels,
        'revenue': revenue,
        'units': units,
    })
    
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
@user_passes_test(is_management)
def remittance_management(request):
    """Main remittance management table listing all organizations and their latest cycle."""
    
    # Latest ledger for each organization (preferring non-PAID first, then latest cycle_start)
    latest_ledger_qs = OrganizationPlatformLedger.objects.filter(
        organization=OuterRef('pk')
    ).order_by('status', '-cycle_start')
    
    organizations_qs = Organization.objects.annotate(
        latest_ledger_id=Subquery(latest_ledger_qs.values('id')[:1]),
        cycle_start=Subquery(latest_ledger_qs.values('cycle_start')[:1]),
        cycle_due=Subquery(latest_ledger_qs.values('cycle_due')[:1]),
        accumulated_sales=Subquery(latest_ledger_qs.values('accumulated_sales')[:1]),
        accumulated_fee=Subquery(latest_ledger_qs.values('accumulated_fee')[:1]),
        status=Subquery(latest_ledger_qs.values('status')[:1]),
        remittance_id=Subquery(latest_ledger_qs.values('remittance__id')[:1]),
    ).order_by('name')

    # Paginate for live server performance
    paginator = Paginator(organizations_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'UTrade_app/management/management_panel/remittance.html',  {
        'page_obj': page_obj, 
    })


@login_required
@user_passes_test(is_management)
@require_POST
def notify_org_remittance(request, ledger_id):
    """Action 1: Notify Organization via chat message."""
    ledger = get_object_or_404(
        OrganizationPlatformLedger.objects.select_related('organization'),
        id=ledger_id,
        status__in=['OPEN', 'DUE'],
    )
    org = ledger.organization
    days = ledger.days_until_due

    # 1. Prepare notification message
    if days < 0:
        msg = (
            f"🚨 REMITTANCE OVERDUE: Your platform fee of ₱{ledger.accumulated_fee} "
            f"was due on {ledger.cycle_due}. Please remit as soon as possible to avoid account restrictions."
        )
    elif days <= 7:
        msg = (
            f"⚠️ REMITTANCE DUE SOON: Your platform fee of ₱{ledger.accumulated_fee} "
            f"is due in {days} day(s) ({ledger.cycle_due}). Please prepare your remittance."
        )
    else:
        msg = (
            f"ℹ️ REMITTANCE NOTICE: Platform fee cycle for {org.name} ends on {ledger.cycle_due}. "
            f"Current accumulated balance: ₱{ledger.accumulated_fee}."
        )

    # 2. Target an officer or member linked to this organization
    target_user = (
        User.objects.filter(org_link=org, is_officer=True).first()
        or User.objects.filter(org_link=org).first()
    )

    if not target_user:
        messages.error(
            request,
            f"Could not send chat: No user account is associated with '{org.name}'."
        )
        return redirect('remittance_management')

    # 3. Get or create direct conversation without requiring a Product
    conversation, _ = Conversation.objects.get_or_create(
        buyer=request.user,
        seller=target_user,
        product=None,
    )

    # 4. Create and store the chat message
    ChatMessage.objects.create(
        conversation=conversation,
        user=request.user,
        content=msg,
        is_read=False,
    )

    # 5. Audit log
    log_action(
        user=request.user,
        action='Remittance Notified',
        item_type='Organization',
        item_name=str(org.name),
        details=f'Sent remittance notification to {target_user.username}: {msg}',
    )

    messages.success(request, f"Notification successfully sent to {org.name} ({target_user.get_short_name}).")
    return redirect('remittance_management')


@login_required
@user_passes_test(is_management)
@require_POST
@transaction.atomic
def record_platform_remittance(request):
    """Action 2 + 3: Mark as Paid + auto-generate receipt and reset cycle."""
    ledger_id = request.POST.get('ledger_id')
    rep_name = (request.POST.get('management_rep_name') or '').strip()

    if not rep_name:
        messages.error(request, 'Management representative name is required.')
        return redirect('remittance_management')

    # Lock row to prevent race conditions from double submission
    ledger = OrganizationPlatformLedger.objects.select_for_update().filter(
        id=ledger_id
    ).first()

    if not ledger or ledger.status == OrganizationPlatformLedger.STATUS_PAID:
        messages.warning(request, 'This remittance cycle is already marked as paid or does not exist.')
        return redirect('remittance_management')

    today = timezone.localdate()
    receipt_no = f'PFR-{today.strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}'

    # Create remittance record
    rem = PlatformFeeRemittance.objects.create(
        ledger=ledger,
        amount_paid=ledger.accumulated_fee,
        payment_date=today,
        due_date=ledger.cycle_due,
        management_rep_name=rep_name,
        recorded_by=request.user,
        receipt_no=receipt_no,
        notes=request.POST.get('notes', ''),
    )

    # Mark current cycle paid
    ledger.status = OrganizationPlatformLedger.STATUS_PAID
    ledger.save(update_fields=['status', 'updated_at'])

    # Reset: create a fresh open cycle starting today (+30 days)
    OrganizationPlatformLedger.objects.create(
        organization=ledger.organization,
        cycle_start=today,
        cycle_due=today + timedelta(days=30),
        status=OrganizationPlatformLedger.STATUS_OPEN,
        accumulated_fee=Decimal('0.00'),
        accumulated_sales=Decimal('0.00'),
    )

    messages.success(request, f'Remittance recorded. Receipt {receipt_no} generated.')
    return redirect('platform_fee_receipt', remittance_id=rem.id)


@login_required
@user_passes_test(is_management)
def platform_fee_receipt(request, remittance_id):
    """View/print platform fee receipt."""
    rem = get_object_or_404(
        PlatformFeeRemittance.objects.select_related('ledger__organization', 'recorded_by'),
        id=remittance_id,
    )
    return render(request, 'UTrade_app/reports/platform_fee_receipt.html', {
        'rem': rem,
        'org': rem.ledger.organization,
    })
    
@login_required
def remittance_logs_view(request):
    # Fetch all ledgers that have been paid/settled
    paid_ledgers = (
        OrganizationPlatformLedger.objects
        .filter(status='PAID')
        .select_related('organization')
        .order_by('-updated_at')
    )
    
    context = {
        'paid_ledgers': paid_ledgers
    }
    return render(request, 'UTrade_app/management/management_panel/remittance_logs.html', context)

@login_required
def view_remittance_receipt(request, ledger_id):
    """
    Renders a printable invoice/receipt for a paid remittance ledger.
    """
    ledger = get_object_or_404(
        OrganizationPlatformLedger.objects.select_related('organization'),
        id=ledger_id
    )
    
    # Fetch all itemized order fee lines attached to this ledger
    fee_lines = PlatformFeeLine.objects.filter(ledger=ledger).select_related('order')

    context = {
        'ledger': ledger,
        'fee_lines': fee_lines,
        'printed_at': timezone.now(),
    }
    return render(request, 'UTrade_app/reports/remittance_receipt.html', context)

@login_required
@user_passes_test(is_management)
def cbrgu_products(request):
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    base_qs = (
        Product.objects
        .filter(seller__user_role='management')
        .select_related('seller', 'category')
        .prefetch_related('variants', 'images', 'reviews')
        .order_by('-created_at')
    )

    if search_query:
        base_qs = base_qs.filter(
            Q(name__icontains=search_query)
            | Q(id__icontains=search_query)
            | Q(product_code__icontains=search_query)
            | Q(seller__first_name__icontains=search_query)
            | Q(seller__last_name__icontains=search_query)
            | Q(seller__username__icontains=search_query)
            | Q(seller__display_name__icontains=search_query)
            | Q(variants__price__icontains=search_query)
            | Q(created_at__icontains=search_query)   # date search (YYYY-MM-DD works)
        ).distinct()

    # Counts
    active_count   = base_qs.filter(status='Approved').count()
    pending_count  = base_qs.filter(status='Pending').count()
    unlisted_count = base_qs.filter(status='Unlisted').count()
    rejected_count = base_qs.filter(status='Rejected').count()

    # Sidebar stats
    total_stocks = sum(p.get_total_stock for p in base_qs)
    total_products = base_qs.count()

    context = {
        'active_products':   base_qs.filter(status='Approved')[:48],
        'pending_products':  base_qs.filter(status='Pending')[:48],
        'unlisted_products': base_qs.filter(status='Unlisted')[:48],
        'rejected_products': base_qs.filter(status='Rejected')[:48],
        'active_count': active_count,
        'pending_count': pending_count,
        'unlisted_count': unlisted_count,
        'rejected_count': rejected_count,
        'status_filter': status_filter,
        # Sidebar
        'products': base_qs,
        'total_stocks': total_stocks,
        'total_orders': 0,          # fill later if you want
        'total_income': 0,          # fill later if you want
        'incoming_preorder_count': 0,
    }
    return render(request, 'UTrade_app/management/management_panel/cbrgu_products.html', context)

@login_required
@user_passes_test(is_management)
def active_listings(request):
    """
    System-wide product management (all sellers).
    Tabs: Active (Approved), Pending, Unlisted, Rejected.
    """
    search_query = request.GET.get('search', '').strip()
    pre_order_filter = request.GET.get('pre_order', '').strip()
    status_filter = request.GET.get('status', '').strip()

    base_qs = (
        Product.objects
        .select_related('seller', 'category')
        .prefetch_related('variants', 'images')
        .order_by('-created_at')
    )

    if search_query:
        base_qs = base_qs.filter(
            Q(name__icontains=search_query)
            | Q(id__icontains=search_query)
            | Q(product_code__icontains=search_query)
            | Q(seller__first_name__icontains=search_query)
            | Q(seller__last_name__icontains=search_query)
            | Q(seller__username__icontains=search_query)
            | Q(seller__display_name__icontains=search_query)
            | Q(variants__price__icontains=search_query)
        ).distinct()

    if pre_order_filter == 'True':
        base_qs = base_qs.filter(pre_order=True)
    elif pre_order_filter == 'False':
        base_qs = base_qs.filter(pre_order=False)

    active_products   = base_qs.filter(status='Approved')
    pending_products  = base_qs.filter(status='Pending')
    unlisted_products = base_qs.filter(status='Unlisted')
    rejected_products = base_qs.filter(status='Rejected')

    context = {
        'active_products': active_products[:100],
        'pending_products': pending_products[:100],
        'unlisted_products': unlisted_products[:100],
        'rejected_products': rejected_products[:100],
        'active_count': active_products.count(),
        'pending_count': pending_products.count(),
        'unlisted_count': unlisted_products.count(),
        'rejected_count': rejected_products.count(),
        'status_filter': status_filter,
        'org_name': 'UTrade Global Management',
    }
    return render(request, 'UTrade_app/management/management_panel/active_listings.html', context)
def _buyer_org_acronym(user):
    """Return BSIT / BSCS style acronym for a buyer."""
    if not user:
        return "—"
    if getattr(user, "course", None):
        return user.course
    org = getattr(user, "org_link", None)
    if org:
        return org.course_code or org.name or "—"
    return "—"


def _notify_seller_chat(admin_user, order, message_text):
    """Send a system chat message to the order's seller about this order."""
    from ..models import Conversation, ChatMessage  # adjust import path if needed

    # Prefer a product from the order items so the conversation is contextual
    product = None
    first_item = order.items.select_related("product_variant__product").first()
    if first_item and first_item.product_variant:
        product = first_item.product_variant.product

    conversation, _ = Conversation.objects.get_or_create(
        product=product,
        buyer=admin_user,
        seller=order.seller,
        defaults={},
    )
    ChatMessage.objects.create(
        conversation=conversation,
        user=admin_user,
        content=message_text,
        is_read=False,
    )


def _send_buyer_order_email(order, action, reason=None):
    """
    Email the buyer (only @cvsu.edu.ph addresses) when an order is accepted or rejected.
    Silently fails if email settings are missing or the address is not campus.
    """
    buyer = order.user
    email = (getattr(buyer, "email", "") or "").strip().lower()
    if not email.endswith("@cvsu.edu.ph"):
        return

    if action == "accept":
        subject = f"UTrade – Order #{order.id} Accepted"
        body = (
            f"Hi {buyer.get_full_name() or buyer.username},\n\n"
            f"Your order #{order.id} (₱{order.total_amount}) has been accepted by Management.\n"
            f"You will be notified when it is ready for pickup.\n\n"
            f"Thank you for using UTrade."
        )
    else:  # reject
        subject = f"UTrade – Order #{order.id} Rejected"
        body = (
            f"Hi {buyer.get_full_name() or buyer.username},\n\n"
            f"Unfortunately your order #{order.id} (₱{order.total_amount}) was rejected.\n"
            f"Reason: {reason or 'Not specified'}\n\n"
            f"You may place a new order or contact Management for clarification.\n\n"
            f"Thank you for using UTrade."
        )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Failed to send order email to %s for order %s", email, order.id)


@login_required
@user_passes_test(is_management)
def management_orders(request):
    """
    Management orders board with filters, Rejected tab, and expanded modals.
    Incoming  = Pending | Paid
    Accepted  = Accepted
    Ready     = Delivered
    Completed = Completed
    Rejected  = Rejected
    """
    search = request.GET.get("search", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    org_filter = request.GET.get("organization", "").strip()

    base = (
        Order.objects
        .filter(seller__user_role="management")
        .select_related("user", "user__org_link", "seller")
        .prefetch_related(
            Prefetch(
                "items",
                queryset=OrderItem.objects.select_related(
                    "product_variant__product"
                ).prefetch_related("product_variant__product__images"),
            )
        )
        .order_by("-created_at")
    )

    if search:
        base = base.filter(
            Q(id__icontains=search)
            | Q(user__username__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__display_name__icontains=search)
            | Q(user__student_no__icontains=search)
        )

    if date_from:
        d = parse_date(date_from)
        if d:
            base = base.filter(created_at__date__gte=d)
    if date_to:
        d = parse_date(date_to)
        if d:
            base = base.filter(created_at__date__lte=d)

    if org_filter:
        base = base.filter(
            Q(user__course__iexact=org_filter)
            | Q(user__org_link__course_code__iexact=org_filter)
            | Q(user__org_link__name__iexact=org_filter)
        )

    incoming_orders = base.filter(status__in=["Pending", "Paid"])
    accepted_orders = base.filter(status="Accepted")
    ready_orders = base.filter(status="Delivered")
    completed_orders = base.filter(status="Completed")
    rejected_orders = base.filter(status="Rejected")

    # Combined list for modals (capped)
    all_for_modals = list(
        list(incoming_orders[:40])
        + list(accepted_orders[:40])
        + list(ready_orders[:40])
        + list(completed_orders[:40])
        + list(rejected_orders[:40])
    )

    # Distinct organization options for the filter dropdown
    org_options = sorted(
        set(
            filter(
                None,
                list(
                    Order.objects.filter(seller__user_role="management")
                    .values_list("user__course", flat=True)
                    .distinct()
                )
                + list(
                    Order.objects.filter(seller__user_role="management")
                    .values_list("user__org_link__course_code", flat=True)
                    .distinct()
                ),
            )
        )
    )

    context = {
        "incoming_orders": incoming_orders[:100],
        "accepted_orders": accepted_orders[:100],
        "ready_orders": ready_orders[:100],
        "completed_orders": completed_orders[:100],
        "rejected_orders": rejected_orders[:100],
        "all_orders_for_modals": all_for_modals,
        "incoming_count": incoming_orders.count(),
        "accepted_count": accepted_orders.count(),
        "ready_count": ready_orders.count(),
        "completed_count": completed_orders.count(),
        "rejected_count": rejected_orders.count(),
        "total_orders": base.count(),
        "org_options": org_options,
        "current_filters": {
            "search": search,
            "date_from": date_from,
            "date_to": date_to,
            "organization": org_filter,
        },
    }
    return render(request, "UTrade_app/management/management_orders/orders.html", context)


@login_required
@user_passes_test(is_management)
@require_POST
def management_orders_batch(request):
    """
    Batch / single order status updates.
    On accept / reject → email buyer (@cvsu.edu.ph).
    On reject → also chat-notify the seller with the reason.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    action = (data.get("action") or "").strip().lower()
    order_ids = data.get("order_ids") or []
    reason = (data.get("reason") or "").strip()

    if not isinstance(order_ids, list) or not order_ids:
        return JsonResponse({"success": False, "message": "No orders selected"}, status=400)
    if len(order_ids) > 20:
        return JsonResponse({"success": False, "message": "Maximum 20 orders per batch"}, status=400)

    allowed = {
        "accept": ("Accepted", ["Pending", "Paid"]),
        "reject": ("Rejected", ["Pending", "Paid"]),
        "ready": ("Delivered", ["Accepted"]),
        "complete": ("Completed", ["Delivered"]),
    }
    if action not in allowed:
        return JsonResponse({"success": False, "message": "Invalid action"}, status=400)

    new_status, from_statuses = allowed[action]
    if action == "reject" and not reason:
        return JsonResponse({"success": False, "message": "Rejection reason required"}, status=400)

    qs = Order.objects.filter(
        id__in=order_ids,
        status__in=from_statuses,
        seller__user_role="management",
    ).select_related("user", "seller").prefetch_related("items__product_variant__product")

    updated = 0
    with transaction.atomic():
        for order in qs.select_for_update():
            order.status = new_status
            if action == "reject":
                order.rejection_reason = reason[:100]
            order.save(
                update_fields=["status", "rejection_reason", "updated_at"]
                if action == "reject"
                else ["status", "updated_at"]
            )
            updated += 1

            log_action(
                user=request.user,
                action=f"Order {action.title()}",
                item_type="Order",
                item_name=f"Order #{order.id}",
                details=f"Status → {new_status}" + (f"; reason={reason}" if reason else ""),
            )

            # Email buyer
            if action in ("accept", "reject"):
                _send_buyer_order_email(order, action, reason=reason if action == "reject" else None)

            # Chat-notify seller on reject
            if action == "reject":
                msg = (
                    f"🚨 SYSTEM (Management): Order #{order.id} from "
                    f"{order.user.get_full_name() or order.user.username} was rejected.\n"
                    f"Reason: {reason}\n"
                    f"Amount: ₱{order.total_amount}"
                )
                try:
                    _notify_seller_chat(request.user, order, msg)
                except Exception:
                    logger.exception("Failed to send chat notification for order %s", order.id)

    if updated == 0:
        return JsonResponse({
            "success": False,
            "message": "No matching orders updated (wrong status or already processed).",
        })

    return JsonResponse({
        "success": True,
        "message": f"{updated} order(s) updated to {new_status}.",
        "updated": updated,
    })

    
    #Pre orders functions --------------
@login_required
@user_passes_test(is_management)
def management_preorders(request):
    """
    Pre-Order Management board.
    Tabs: Incoming → Accepted → Processing / Awaiting Payment / Waiting for Stocks
          → Ready for Pickup → Completed | Rejected
    """
    search = request.GET.get("search", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    org_filter = request.GET.get("organization", "").strip()

    base = (
        PreOrderRequest.objects
        .filter(seller__user_role="management")
        .select_related(
            "buyer", "buyer__org_link",
            "seller",
            "product_variant", "product_variant__product",
        )
        .prefetch_related("product_variant__product__images")
        .order_by("-created_at")
    )

    if search:
        base = base.filter(
            Q(id__icontains=search)
            | Q(buyer__username__icontains=search)
            | Q(buyer__first_name__icontains=search)
            | Q(buyer__last_name__icontains=search)
            | Q(buyer__student_no__icontains=search)
            | Q(product_variant__product__name__icontains=search)
            | Q(full_name_at_time__icontains=search)
        )

    if date_from:
        d = parse_date(date_from)
        if d:
            base = base.filter(created_at__date__gte=d)
    if date_to:
        d = parse_date(date_to)
        if d:
            base = base.filter(created_at__date__lte=d)

    if org_filter:
        base = base.filter(
            Q(buyer__course__iexact=org_filter)
            | Q(buyer__org_link__course_code__iexact=org_filter)
            | Q(course_at_time__iexact=org_filter)
        )

    incoming = base.filter(status="PENDING")
    accepted = base.filter(status="ACCEPTED")
    processing = base.filter(status="PROCESSING")
    awaiting_payment = base.filter(status="AWAITING_PAYMENT")
    waiting_stocks = base.filter(status="WAITING_STOCKS")
    ready = base.filter(status="READY")
    completed = base.filter(status="COMPLETED")
    rejected = base.filter(status="REJECTED")

    all_for_modals = list(
        list(incoming[:30])
        + list(accepted[:30])
        + list(processing[:30])
        + list(awaiting_payment[:30])
        + list(waiting_stocks[:30])
        + list(ready[:30])
        + list(completed[:30])
        + list(rejected[:30])
    )

    org_options = sorted(
        set(
            filter(
                None,
                list(base.values_list("buyer__course", flat=True).distinct())
                + list(base.values_list("course_at_time", flat=True).distinct())
                + list(base.values_list("buyer__org_link__course_code", flat=True).distinct()),
            )
        )
    )

    context = {
        "incoming_preorders": incoming[:100],
        "accepted_preorders": accepted[:100],
        "processing_preorders": processing[:100],
        "awaiting_payment_preorders": awaiting_payment[:100],
        "waiting_stocks_preorders": waiting_stocks[:100],
        "ready_preorders": ready[:100],
        "completed_preorders": completed[:100],
        "rejected_preorders": rejected[:100],
        "all_preorders_for_modals": all_for_modals,
        "incoming_count": incoming.count(),
        "accepted_count": accepted.count(),
        "processing_count": processing.count(),
        "awaiting_payment_count": awaiting_payment.count(),
        "waiting_stocks_count": waiting_stocks.count(),
        "ready_count": ready.count(),
        "completed_count": completed.count(),
        "rejected_count": rejected.count(),
        "total_preorders": base.count(),
        "org_options": org_options,
        "current_filters": {
            "search": search,
            "date_from": date_from,
            "date_to": date_to,
            "organization": org_filter,
        },
    }
    return render(
        request,
        "UTrade_app/management/management_orders/pre_orders.html",
        context,
    )


@login_required
@user_passes_test(is_management)
@require_POST
def management_preorders_batch(request):
    """
    Batch / single status updates for pre-orders.
    Actions: accept | reject | processing | awaiting_payment | waiting_stocks | ready | complete
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    action = (data.get("action") or "").strip().lower()
    preorder_ids = data.get("order_ids") or data.get("preorder_ids") or []
    reason = (data.get("reason") or "").strip()
    note = (data.get("note") or "").strip()

    if not isinstance(preorder_ids, list) or not preorder_ids:
        return JsonResponse({"success": False, "message": "No pre-orders selected"}, status=400)
    if len(preorder_ids) > 20:
        return JsonResponse({"success": False, "message": "Maximum 20 pre-orders per batch"}, status=400)

    allowed = {
        "accept": ("ACCEPTED", ["PENDING"]),
        "reject": ("REJECTED", ["PENDING"]),
        "processing": ("PROCESSING", ["ACCEPTED"]),
        "awaiting_payment": ("AWAITING_PAYMENT", ["ACCEPTED"]),
        "waiting_stocks": ("WAITING_STOCKS", ["ACCEPTED"]),
        "ready": ("READY", ["PROCESSING", "AWAITING_PAYMENT", "WAITING_STOCKS"]),
        "complete": ("COMPLETED", ["READY"]),
    }
    if action not in allowed:
        return JsonResponse({"success": False, "message": "Invalid action"}, status=400)

    new_status, from_statuses = allowed[action]
    if action == "reject" and not reason:
        return JsonResponse({"success": False, "message": "Rejection reason required"}, status=400)

    qs = PreOrderRequest.objects.filter(
        id__in=preorder_ids,
        status__in=from_statuses,
        seller__user_role="management",
    ).select_related("buyer", "seller", "product_variant__product")

    updated = 0
    with transaction.atomic():
        for po in qs.select_for_update():
            po.status = new_status
            if action == "reject":
                po.rejection_reason = reason[:100]
                if reason == "Other" and note:
                    po.rejection_note = note[:500]
            po.save()
            updated += 1

            log_action(
                user=request.user,
                action=f"PreOrder {action.title()}",
                item_type="PreOrder",
                item_name=f"PreOrder #{po.id}",
                details=f"Status → {new_status}" + (f"; reason={reason}" if reason else ""),
            )

    if updated == 0:
        return JsonResponse({
            "success": False,
            "message": "No matching pre-orders updated (wrong status or already processed).",
        })

    return JsonResponse({
        "success": True,
        "message": f"{updated} pre-order(s) updated to {new_status}.",
        "updated": updated,
    })