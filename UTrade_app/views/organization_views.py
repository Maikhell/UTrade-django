import json
import logging
import re
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from django.views.generic import UpdateView
from xhtml2pdf import pisa

from ..forms import ProductForm
from ..models import (
    Category,
    ChatMessage,
    Conversation,
    MeetupLocation,
    Order,
    OrderItem,
    Organization,
    OrganizationPlatformLedger,
    PlatformFeeLine,
    PlatformFeeRemittance,
    PreOrderRequest,
    Product,
    ProductImage,
    ProductVariant,
    User,
)
from ..utils import log_action

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------

def is_organization(user):
    """True if user is an org officer (or org_officer role) with an org_link."""
    if not user or not user.is_authenticated:
        return False
    role = getattr(user, "user_role", None)
    is_officer = getattr(user, "is_officer", False)
    has_org = bool(getattr(user, "org_link_id", None))
    return has_org and (role == "org_officer" or is_officer)


def _require_org(user):
    """Return the Organization instance or None."""
    if not is_organization(user):
        return None
    return user.org_link


def _org_product_qs(user):
    """Products belonging to the logged-in organization."""
    org = _require_org(user)
    if not org:
        return Product.objects.none()
    return Product.objects.filter(
        Q(seller=user) | Q(seller__org_link=org)
    ).distinct()


def _org_order_qs(user):
    """Orders where the seller is in the same organization."""
    org = _require_org(user)
    if not org:
        return Order.objects.none()
    return Order.objects.filter(
        Q(seller=user) | Q(seller__org_link=org)
    ).distinct()


def _org_preorder_qs(user):
    """Pre-orders where the seller is in the same organization."""
    org = _require_org(user)
    if not org:
        return PreOrderRequest.objects.none()
    return PreOrderRequest.objects.filter(
        Q(seller=user) | Q(seller__org_link=org)
    ).distinct()


def _sidebar_context(user):
    products = _org_product_qs(user)
    total_stocks = 0
    try:
        total_stocks = sum(getattr(p, "get_total_stock", 0) or 0 for p in products)
    except Exception:
        total_stocks = 0

    orders = _org_order_qs(user)
    completed = orders.filter(status="Completed")
    total_income = completed.aggregate(s=Sum("total_amount"))["s"] or Decimal("0.00")

    incoming_pre = _org_preorder_qs(user).filter(
        status__in=["PENDING", "Pending", "pending"]
    ).count()

    return {
        "products": products,
        "total_stocks": total_stocks,
        "total_orders": orders.count(),
        "total_income": total_income,
        "incoming_preorder_count": incoming_pre,
        "org": _require_org(user),
    }


# ---------------------------------------------------------------------------
# Existing org status helper
# ---------------------------------------------------------------------------

def update_status_org(request, item_type, item_id):
    requested_status = request.GET.get("status")
    if item_type == "user" and requested_status == "approved":
        final_status = "verified"
    else:
        final_status = requested_status

    if item_type == "user":
        obj = get_object_or_404(User, id=item_id)
        obj.status = final_status
        obj.save()
        messages.success(
            request, f"Student {obj.get_full_name()} is now {final_status}."
        )
    elif item_type == "product":
        obj = get_object_or_404(Product, id=item_id)
        # Scope to org
        if obj.seller_id != request.user.id and getattr(
            obj.seller, "org_link_id", None
        ) != getattr(request.user, "org_link_id", None):
            messages.error(request, "You cannot update this product.")
            return redirect("organization.panel")
        obj.status = requested_status
        obj.save()
        messages.success(request, f"Product '{obj.name}' has been {requested_status}.")

    return redirect("organization.panel")


# ---------------------------------------------------------------------------
# Product update (class-based)
# ---------------------------------------------------------------------------

class OrgProductUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "UTrade_app/organization/actions/edit_product.html"

    def test_func(self):
        obj = self.get_object()
        user = self.request.user
        if not is_organization(user):
            return False
        if obj.seller_id == user.id:
            return True
        return (
            getattr(obj.seller, "org_link_id", None) == user.org_link_id
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        selected_days = [
            d.strip() for d in (product.available_days or "").split(",") if d.strip()
        ]
        context.update({
            "product": product,
            "categories": Category.objects.all().order_by("name"),
            "meetup_locations": MeetupLocation.objects.all().order_by("name"),
            "selected_days": selected_days,
            "days_choices": [
                ("Monday", "Mon"),
                ("Tuesday", "Tue"),
                ("Wednesday", "Wed"),
                ("Thursday", "Thu"),
                ("Friday", "Fri"),
                ("Saturday", "Sat"),
            ],
            **_sidebar_context(self.request.user),
        })
        return context

    def form_valid(self, form):
        product = form.save(commit=False)
        product.status = "Pending"
        product.save()

        variants_raw = (
            self.request.POST.get("variants_json")
            or self.request.POST.get("variants")
        )
        if variants_raw:
            try:
                variants = json.loads(variants_raw)
            except json.JSONDecodeError:
                variants = []
            for v in variants:
                vid = v.get("id")
                payload = {
                    "variant_name": v.get("name", ""),
                    "attribute_value": v.get("attribute", ""),
                    "price": v.get("price") or 0,
                    "stocks": v.get("stock") or 0,
                    "condition": v.get("condition", "Brand New"),
                    "flaws_description": v.get("flaws", ""),
                }
                if vid:
                    ProductVariant.objects.filter(id=vid, product=product).update(
                        **payload
                    )
                else:
                    ProductVariant.objects.create(product=product, **payload)

        messages.warning(
            self.request,
            f'“{product.name}” was updated and sent back for approval.',
        )
        return redirect("organization.panel")


# ---------------------------------------------------------------------------
# Product details / edit
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_organization)
def org_product_details(request, product_id):
    product = get_object_or_404(
        _org_product_qs(request.user)
        .select_related("seller", "category")
        .prefetch_related("variants", "images"),
        id=product_id,
    )

    meetup_location = (product.meetup_location_text or "").strip()
    raw_days = (product.available_days or "").strip()
    available_days_list = [
        day.strip() for day in raw_days.split(",") if day.strip()
    ] if raw_days else []

    return render(
        request,
        "UTrade_app/organization/organization_panel/product_view.html",
        {
            "product": product,
            "meetup_location": meetup_location,
            "available_days_list": available_days_list,
            "meetup_time_from": product.preferred_meetup_time_from,
            "meetup_time_to": product.preferred_meetup_time_to,
            **_sidebar_context(request.user),
        },
    )


@login_required
@user_passes_test(is_organization)
def org_product_edit(request, pk):
    """Edit org product; sets status to Pending after save."""
    product = get_object_or_404(
        _org_product_qs(request.user)
        .select_related("category", "seller")
        .prefetch_related("variants", "images"),
        pk=pk,
    )

    if request.method == "POST":
        return _save_org_product_edit(request, product)

    selected_days = [
        d.strip() for d in (product.available_days or "").split(",") if d.strip()
    ]
    context = {
        "product": product,
        "categories": Category.objects.all().order_by("name"),
        "meetup_locations": MeetupLocation.objects.all().order_by("name"),
        "selected_days": selected_days,
        "days_choices": [
            ("Monday", "Mon"),
            ("Tuesday", "Tue"),
            ("Wednesday", "Wed"),
            ("Thursday", "Thu"),
            ("Friday", "Fri"),
            ("Saturday", "Sat"),
        ],
        **_sidebar_context(request.user),
    }
    return render(
        request,
        "UTrade_app/organization/actions/edit_product.html",
        context,
    )


@transaction.atomic
def _save_org_product_edit(request, product):
    data = request.POST

    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    if not name or not description:
        messages.error(request, "Name and description are required.")
        return redirect("org_product_edit", pk=product.pk)

    product.name = name
    product.description = description

    cat_id = data.get("category")
    if cat_id:
        product.category_id = cat_id

    product.meetup_location_text = (data.get("meetup_location_text") or "").strip()
    days = data.getlist("available_days")
    product.available_days = ",".join(days) if days else ""

    product.preferred_meetup_time_from = data.get("preferred_meetup_time_from") or None
    product.preferred_meetup_time_to = data.get("preferred_meetup_time_to") or None
    product.owner_type = data.get("owner_type") or product.owner_type
    product.accepted_payments = data.get("accepted_payments") or product.accepted_payments
    product.pre_order = data.get("is_pre_order") == "on"

    product.status = "Pending"
    product.save()

    delete_ids = [
        x for x in (data.get("delete_image_ids") or "").split(",") if x.isdigit()
    ]
    if delete_ids:
        ProductImage.objects.filter(product=product, id__in=delete_ids).delete()

    for f in request.FILES.getlist("images"):
        ProductImage.objects.create(product=product, image=f)

    raw = data.get("variants_json") or "[]"
    try:
        variants = json.loads(raw)
    except json.JSONDecodeError:
        variants = []

    keep_ids = []
    for v in variants:
        vid = v.get("id")
        payload = {
            "variant_name": (v.get("name") or "")[:100],
            "attribute_value": (v.get("attribute") or "")[:100],
            "price": v.get("price") or 0,
            "stocks": int(v.get("stock") or 0),
            "condition": v.get("condition") or "Brand New",
            "flaws_description": v.get("flaws") or "",
        }
        if vid:
            updated = ProductVariant.objects.filter(id=vid, product=product).update(
                **payload
            )
            if updated:
                keep_ids.append(int(vid))
        else:
            obj = ProductVariant.objects.create(product=product, **payload)
            keep_ids.append(obj.id)

    ProductVariant.objects.filter(product=product).exclude(id__in=keep_ids).delete()

    log_action(
        user=request.user,
        action="Product Updated",
        item_type="Product",
        item_name=product.name,
        details=f"Org edit ID:{product.id}; status set to Pending.",
    )
    messages.warning(
        request,
        f'“{product.name}” was updated and sent back for approval. '
        f"It is hidden until approved again.",
    )
    return redirect("organization.panel")


@login_required
@require_POST
@user_passes_test(is_organization)
def org_variant_delete(request, pk):
    variant = get_object_or_404(
        ProductVariant,
        pk=pk,
        product__in=_org_product_qs(request.user),
    )
    product = variant.product
    variant.delete()
    if product.status == "Approved":
        product.status = "Pending"
        product.save(update_fields=["status"])
        notice = "Variant removed. Product returned to Pending for re-approval."
    else:
        notice = "Variant removed."

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "success", "message": notice})
    messages.success(request, notice)
    return redirect("organization.panel")


# ---------------------------------------------------------------------------
# Org products board (like cbrgu_products)
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_organization)
def org_products(request):
    search_query = request.GET.get("search", "").strip()
    status_filter = request.GET.get("status", "").strip()

    base_qs = (
        _org_product_qs(request.user)
        .select_related("seller", "category")
        .prefetch_related("variants", "images")
        .order_by("-created_at")
    )

    if search_query:
        base_qs = base_qs.filter(
            Q(name__icontains=search_query)
            | Q(id__icontains=search_query)
            | Q(product_code__icontains=search_query)
            | Q(variants__price__icontains=search_query)
        ).distinct()

    context = {
        "active_products": base_qs.filter(status="Approved")[:48],
        "pending_products": base_qs.filter(status="Pending")[:48],
        "unlisted_products": base_qs.filter(status="Unlisted")[:48],
        "rejected_products": base_qs.filter(status="Rejected")[:48],
        "active_count": base_qs.filter(status="Approved").count(),
        "pending_count": base_qs.filter(status="Pending").count(),
        "unlisted_count": base_qs.filter(status="Unlisted").count(),
        "rejected_count": base_qs.filter(status="Rejected").count(),
        "status_filter": status_filter,
        **_sidebar_context(request.user),
    }
    return render(
        request,
        "UTrade_app/organization/organization_panel/products.html",
        context,
    )


@login_required
@user_passes_test(is_organization)
@require_POST
def org_unlist_product(request, product_id):
    product = get_object_or_404(
        _org_product_qs(request.user), id=product_id, status="Approved"
    )
    reason = (request.POST.get("reason") or "Unlisted by organization").strip()
    product.status = "Unlisted"
    product.save(update_fields=["status"])
    log_action(
        user=request.user,
        action="Product Unlisted",
        item_type="Product",
        item_name=product.name,
        details=f"Org unlisted ID:{product.id}. Reason: {reason}",
    )
    messages.success(request, f'“{product.name}” has been unlisted.')
    return redirect("org_products")


@login_required
@user_passes_test(is_organization)
@require_POST
def org_list_product(request, product_id):
    product = get_object_or_404(
        _org_product_qs(request.user), id=product_id, status="Unlisted"
    )
    product.status = "Approved"
    product.save(update_fields=["status"])
    log_action(
        user=request.user,
        action="Product Listed",
        item_type="Product",
        item_name=product.name,
        details=f"Org re-listed ID:{product.id} as Approved.",
    )
    messages.success(request, f'“{product.name}” is now active on the marketplace.')
    return redirect("org_products")


# ---------------------------------------------------------------------------
# Notification helpers (org-scoped wording)
# ---------------------------------------------------------------------------

def _buyer_org_acronym(user):
    if not user:
        return "—"
    if getattr(user, "course", None):
        return user.course
    org = getattr(user, "org_link", None)
    if org:
        return org.course_code or org.name or "—"
    return "—"


def _notify_seller_chat(actor, order, message_text):
    product = None
    first_item = order.items.select_related("product_variant__product").first()
    if first_item and first_item.product_variant:
        product = first_item.product_variant.product

    conversation, _ = Conversation.objects.get_or_create(
        product=product,
        buyer=actor,
        seller=order.seller,
        defaults={},
    )
    ChatMessage.objects.create(
        conversation=conversation,
        user=actor,
        content=message_text,
        is_read=False,
    )


def _notify_buyer_chat(actor, preorder, message_text):
    product = None
    if preorder.product_variant_id:
        product = preorder.product_variant.product

    conversation, _ = Conversation.objects.get_or_create(
        product=product,
        buyer=preorder.buyer,
        seller=actor,
    )
    ChatMessage.objects.create(
        conversation=conversation,
        user=actor,
        content=message_text,
        is_read=False,
    )


def _send_buyer_order_email(order, action, reason=None, org_name="Organization"):
    buyer = order.user
    email = (getattr(buyer, "email", "") or "").strip().lower()
    if not email.endswith("@cvsu.edu.ph"):
        return

    if action == "accept":
        subject = f"UTrade – Order #{order.id} Accepted"
        body = (
            f"Hi {buyer.get_full_name() or buyer.username},\n\n"
            f"Your order #{order.id} (₱{order.total_amount}) has been accepted by {org_name}.\n"
            f"You will be notified when it is ready for pickup.\n\n"
            f"Thank you for using UTrade."
        )
    else:
        subject = f"UTrade – Order #{order.id} Rejected"
        body = (
            f"Hi {buyer.get_full_name() or buyer.username},\n\n"
            f"Unfortunately your order #{order.id} (₱{order.total_amount}) was rejected by {org_name}.\n"
            f"Reason: {reason or 'Not specified'}\n\n"
            f"You may place a new order or contact the organization for clarification.\n\n"
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
        logger.exception(
            "Failed to send order email to %s for order %s", email, order.id
        )


def _send_buyer_preorder_email(preorder, event, extra=None, org_name="Organization"):
    buyer = preorder.buyer
    email = (getattr(buyer, "email", "") or "").strip().lower()
    if not email.endswith("@cvsu.edu.ph"):
        return

    name = buyer.get_full_name() or buyer.username
    product_name = (
        preorder.product_variant.product.name
        if preorder.product_variant_id and preorder.product_variant.product_id
        else "your item"
    )
    total = preorder.get_total_price() if hasattr(preorder, "get_total_price") else ""

    if event == "accept":
        subject = f"UTrade – Pre-Order #{preorder.id} Accepted"
        est = extra or getattr(preorder, "estimated_pickup", None) or "to be confirmed"
        body = (
            f"Hi {name},\n\n"
            f"Your pre-order #{preorder.id} for {product_name} (₱{total}) has been accepted by {org_name}.\n"
            f"Estimated ready for pickup: {est}.\n\n"
            f"You will be notified when it is ready.\n\n"
            f"Thank you for using UTrade."
        )
    elif event == "ready":
        subject = f"UTrade – Pre-Order #{preorder.id} Ready for Pickup"
        body = (
            f"Hi {name},\n\n"
            f"Your pre-order #{preorder.id} for {product_name} (₱{total}) is ready for pickup.\n"
            f"Please proceed to the designated meetup location.\n\n"
            f"Thank you for using UTrade."
        )
    else:
        return

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception:
        logger.exception(
            "Failed preorder email to %s for #%s", email, preorder.id
        )


# ---------------------------------------------------------------------------
# Organization Orders
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_organization)
def organization_orders(request):
    """
    Org orders board — only orders for this organization.
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
        _org_order_qs(request.user)
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

    all_for_modals = list(
        list(incoming_orders[:40])
        + list(accepted_orders[:40])
        + list(ready_orders[:40])
        + list(completed_orders[:40])
        + list(rejected_orders[:40])
    )

    org_options = sorted(
        set(
            filter(
                None,
                list(base.values_list("user__course", flat=True).distinct())
                + list(
                    base.values_list("user__org_link__course_code", flat=True).distinct()
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
        **_sidebar_context(request.user),
    }
    return render(
        request,
        "UTrade_app/organization/organization_orders/orders.html",
        context,
    )


@login_required
@user_passes_test(is_organization)
@require_POST
def organization_orders_batch(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    action = (data.get("action") or "").strip().lower()
    order_ids = data.get("order_ids") or []
    reason = (data.get("reason") or "").strip()

    if not isinstance(order_ids, list) or not order_ids:
        return JsonResponse(
            {"success": False, "message": "No orders selected"}, status=400
        )
    if len(order_ids) > 20:
        return JsonResponse(
            {"success": False, "message": "Maximum 20 orders per batch"}, status=400
        )

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
        return JsonResponse(
            {"success": False, "message": "Rejection reason required"}, status=400
        )

    org = _require_org(request.user)
    org_name = org.name if org else "Organization"

    qs = (
        _org_order_qs(request.user)
        .filter(id__in=order_ids, status__in=from_statuses)
        .select_related("user", "seller")
        .prefetch_related("items__product_variant__product")
    )

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
                details=f"Status → {new_status}"
                + (f"; reason={reason}" if reason else ""),
            )

            if action in ("accept", "reject"):
                _send_buyer_order_email(
                    order,
                    action,
                    reason=reason if action == "reject" else None,
                    org_name=org_name,
                )

            if action == "reject":
                msg = (
                    f"🚨 SYSTEM ({org_name}): Order #{order.id} from "
                    f"{order.user.get_full_name() or order.user.username} was rejected.\n"
                    f"Reason: {reason}\n"
                    f"Amount: ₱{order.total_amount}"
                )
                try:
                    _notify_seller_chat(request.user, order, msg)
                except Exception:
                    logger.exception(
                        "Failed chat notification for order %s", order.id
                    )

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


# ---------------------------------------------------------------------------
# Organization Pre-Orders
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_organization)
def organization_preorders(request):
    search = request.GET.get("search", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    org_filter = request.GET.get("organization", "").strip()

    base = (
        _org_preorder_qs(request.user)
        .select_related(
            "buyer",
            "buyer__org_link",
            "seller",
            "product_variant",
            "product_variant__product",
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

    incoming = base.filter(status__in=["PENDING", "Pending", "pending"])
    accepted = base.filter(
        status__in=["ACCEPTED", "APPROVED", "Accepted", "Approved"]
    )
    processing = base.filter(
        status__in=["PROCESSING", "PREPARING", "Processing", "Preparing"]
    )
    awaiting_payment = base.filter(
        status__in=["AWAITING_PAYMENT", "Awaiting Payment"]
    )
    waiting_stocks = base.filter(
        status__in=["WAITING_STOCKS", "Waiting for Stocks"]
    )
    ready = base.filter(status__in=["READY", "Ready", "Ready for Pickup"])
    completed = base.filter(status__in=["COMPLETED", "Completed"])
    rejected = base.filter(
        status__in=["REJECTED", "DECLINED", "Rejected", "Declined"]
    )

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
                + list(
                    base.values_list(
                        "buyer__org_link__course_code", flat=True
                    ).distinct()
                ),
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
        **_sidebar_context(request.user),
    }
    return render(
        request,
        "UTrade_app/organization/organization_orders/pre_orders.html",
        context,
    )


@login_required
@user_passes_test(is_organization)
@require_POST
def organization_preorders_batch(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    action = (data.get("action") or "").strip().lower()
    preorder_ids = data.get("order_ids") or data.get("preorder_ids") or []
    reason = (data.get("reason") or "").strip()
    note = (data.get("note") or "").strip()
    estimated_pickup = (data.get("estimated_pickup") or "").strip()

    if not isinstance(preorder_ids, list) or not preorder_ids:
        return JsonResponse(
            {"success": False, "message": "No pre-orders selected"}, status=400
        )
    if len(preorder_ids) > 20:
        return JsonResponse(
            {"success": False, "message": "Maximum 20 pre-orders per batch"},
            status=400,
        )

    MID = [
        "ACCEPTED",
        "APPROVED",
        "Accepted",
        "Approved",
        "PROCESSING",
        "PREPARING",
        "Processing",
        "Preparing",
        "AWAITING_PAYMENT",
        "Awaiting Payment",
        "WAITING_STOCKS",
        "Waiting for Stocks",
    ]

    allowed = {
        "accept": ("ACCEPTED", ["PENDING", "Pending", "pending"]),
        "reject": ("REJECTED", ["PENDING", "Pending", "pending"]),
        "processing": ("PROCESSING", MID),
        "awaiting_payment": ("AWAITING_PAYMENT", MID),
        "waiting_stocks": ("WAITING_STOCKS", MID),
        "ready": (
            "READY",
            [
                "PROCESSING",
                "PREPARING",
                "Processing",
                "Preparing",
                "AWAITING_PAYMENT",
                "Awaiting Payment",
                "WAITING_STOCKS",
                "Waiting for Stocks",
                "ACCEPTED",
                "APPROVED",
                "Accepted",
                "Approved",
            ],
        ),
        "complete": ("COMPLETED", ["READY", "Ready", "Ready for Pickup"]),
        "set_estimate": (None, MID + ["READY", "Ready", "Ready for Pickup"]),
    }

    if action not in allowed:
        return JsonResponse({"success": False, "message": "Invalid action"}, status=400)

    new_status, from_statuses = allowed[action]

    if action == "reject" and not reason:
        return JsonResponse(
            {"success": False, "message": "Rejection reason required"}, status=400
        )
    if action == "set_estimate" and not estimated_pickup:
        return JsonResponse(
            {"success": False, "message": "Estimated pickup required"}, status=400
        )

    org = _require_org(request.user)
    org_name = org.name if org else "Organization"

    qs = (
        _org_preorder_qs(request.user)
        .filter(id__in=preorder_ids, status__in=from_statuses)
        .select_related("buyer", "seller", "product_variant__product")
    )

    updated = 0
    with transaction.atomic():
        for po in qs.select_for_update():
            if action == "set_estimate":
                po.estimated_pickup = estimated_pickup[:50]
                po.save(update_fields=["estimated_pickup", "updated_at"])
            else:
                po.status = new_status
                fields = ["status", "updated_at"]
                if action == "reject":
                    po.rejection_reason = reason[:100]
                    fields.append("rejection_reason")
                    if reason == "Other" and note:
                        po.rejection_note = note[:500]
                        fields.append("rejection_note")
                if action == "accept" and estimated_pickup:
                    po.estimated_pickup = estimated_pickup[:50]
                    fields.append("estimated_pickup")
                po.save(update_fields=fields)

            updated += 1

            log_action(
                user=request.user,
                action=f"PreOrder {action.title()}",
                item_type="PreOrder",
                item_name=f"PreOrder #{po.id}",
                details=(
                    f"Status → {new_status or po.status}"
                    + (f"; reason={reason}" if reason else "")
                    + (f"; estimate={estimated_pickup}" if estimated_pickup else "")
                ),
            )

            try:
                if action == "accept":
                    est = estimated_pickup or po.estimated_pickup or "to be confirmed"
                    msg = (
                        f"✅ SYSTEM ({org_name}): Your pre-order #{po.id} has been accepted.\n"
                        f"Estimated ready for pickup: {est}."
                    )
                    _notify_buyer_chat(request.user, po, msg)
                    _send_buyer_preorder_email(
                        po, "accept", extra=est, org_name=org_name
                    )
                elif action == "ready":
                    msg = (
                        f"📦 SYSTEM ({org_name}): Your pre-order #{po.id} is ready for pickup.\n"
                        f"Please proceed to the designated meetup location."
                    )
                    _notify_buyer_chat(request.user, po, msg)
                    _send_buyer_preorder_email(po, "ready", org_name=org_name)
            except Exception:
                logger.exception("Notify failed for preorder %s", po.id)

    if updated == 0:
        return JsonResponse({
            "success": False,
            "message": "No matching pre-orders updated (wrong status or already processed).",
        })

    return JsonResponse({
        "success": True,
        "message": f"{updated} pre-order(s) updated.",
        "updated": updated,
    })


# ---------------------------------------------------------------------------
# Org dashboard / sales chart
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_organization)
def organization_panel(request):
    """
    Organization dashboard — stats + Chart.js data scoped to this org only.
    """
    user = request.user
    org = _require_org(user)
    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)
    default_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    default_zeros = [0, 0, 0, 0, 0, 0, 0]

    products = _org_product_qs(user)
    seller_orders = _org_order_qs(user)
    seller_preorders = (
        _org_preorder_qs(user)
        .select_related("buyer", "product_variant", "product_variant__product")
        .order_by("-id")
    )

    # ---- Orders by status ----
    incoming_orders_qs = seller_orders.filter(status__in=["Pending", "Paid"])
    accepted_orders_qs = seller_orders.filter(status="Accepted")
    ready_orders_qs = seller_orders.filter(status="Delivered")
    completed_orders_qs = seller_orders.filter(status="Completed")

    # Items from completed orders (this org’s products only)
    completed_items = OrderItem.objects.filter(
        order__in=completed_orders_qs,
        product_variant__product__in=products,
    )

    # ---- Pre-orders by status ----
    incoming_preorders_qs = seller_preorders.filter(
        status__in=["PENDING", "Pending", "pending"]
    )
    ready_preorders_qs = seller_preorders.filter(
        status__in=["READY", "Ready", "Ready for Pickup", "ACCEPTED", "Accepted"]
    )
    completed_preorders_qs = seller_preorders.filter(
        status__in=["COMPLETED", "Completed"]
    )

    # ---- Stocks ----
    try:
        total_stocks = (
            ProductVariant.objects.filter(product__in=products).aggregate(
                total=Sum("stocks")
            )["total"]
        ) or 0
    except Exception:
        total_stocks = (
            ProductVariant.objects.filter(product__in=products).aggregate(
                total=Sum("stock")
            )["total"]
        ) or 0

    total_orders = seller_orders.count()
    total_preorders = seller_preorders.count()
    total_income = completed_items.aggregate(
        total=Sum(F("price") * F("quantity"))
    )["total"] or Decimal("0.00")

    # ---- Revenue last 7 days ----
    revenue_daily = (
        completed_items.filter(order__created_at__gte=seven_days_ago)
        .annotate(date=TruncDate("order__created_at"))
        .values("date")
        .annotate(daily_revenue=Sum(F("price") * F("quantity")))
        .order_by("date")
    )
    revenue_labels = [r["date"].strftime("%a") for r in revenue_daily if r["date"]]
    revenue_data = [float(r["daily_revenue"] or 0) for r in revenue_daily]

    # ---- Top products ----
    top_products_qs = (
        completed_items.values("product_variant__product__name")
        .annotate(total_units=Sum("quantity"))
        .order_by("-total_units")[:5]
    )
    top_products_labels = [
        p["product_variant__product__name"] or "Unknown" for p in top_products_qs
    ]
    top_products_data = [p["total_units"] or 0 for p in top_products_qs]

    # ---- Orders over time ----
    orders_daily = (
        seller_orders.filter(created_at__gte=seven_days_ago)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(order_count=Count("id"))
        .order_by("date")
    )
    orders_over_time_labels = [
        o["date"].strftime("%a") for o in orders_daily if o["date"]
    ]
    orders_over_time_data = [o["order_count"] for o in orders_daily]

    # ---- Pre-orders over time ----
    preorders_daily = (
        seller_preorders.filter(created_at__gte=seven_days_ago)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(order_count=Count("id"))
        .order_by("date")
    )
    preorders_over_time_labels = [
        o["date"].strftime("%a") for o in preorders_daily if o["date"]
    ]
    preorders_over_time_data = [o["order_count"] for o in preorders_daily]

    context = {
        "org": org,
        "org_name": org.name if org else "Organization",
        "products": products,
        "total_stocks": total_stocks,
        "total_orders": total_orders,
        "total_preorders": total_preorders,
        "total_income": f"{total_income:,.2f}",
        "active_products_count": products.filter(status="Approved").count(),
        "pending_products_count": products.filter(status="Pending").count(),
        "incoming_orders_count": incoming_orders_qs.count(),
        "accepted_orders_count": accepted_orders_qs.count(),
        "ready_orders_count": ready_orders_qs.count(),
        "completed_orders_count": completed_orders_qs.count(),
        "incoming_preorder_count": incoming_preorders_qs.count(),
        "ready_preorder_count": ready_preorders_qs.count(),
        "completed_preorder_count": completed_preorders_qs.count(),
        "recent_orders": seller_orders.order_by("-created_at")[:10],
        # Chart JSON (always valid arrays so Chart.js never breaks)
        "revenue_labels_json": json.dumps(revenue_labels or default_days),
        "revenue_data_json": json.dumps(revenue_data or default_zeros),
        "top_products_labels_json": json.dumps(
            top_products_labels or ["No Sales Yet"]
        ),
        "top_products_data_json": json.dumps(top_products_data or [0]),
        "orders_over_time_labels_json": json.dumps(
            orders_over_time_labels or default_days
        ),
        "orders_over_time_data_json": json.dumps(
            orders_over_time_data or default_zeros
        ),
        "preorders_over_time_labels_json": json.dumps(
            preorders_over_time_labels or default_days
        ),
        "preorders_over_time_data_json": json.dumps(
            preorders_over_time_data or default_zeros
        ),
    }
    return render(
        request,
        "UTrade_app/organization/organization_panel/dashboard.html",
        context,
    )


@login_required
@user_passes_test(is_organization)
def org_sales_chart_data(request):
    """JSON for Chart.js — completed orders for this org only."""
    user = request.user
    days = int(request.GET.get("days", 30))
    since = timezone.now() - timedelta(days=days)

    qs = (
        OrderItem.objects.filter(
            product_variant__product__in=_org_product_qs(user),
            order__status__iexact="Completed",
            order__updated_at__gte=since,
        )
        .annotate(day=TruncDate("order__updated_at"))
        .values("day")
        .annotate(
            revenue=Sum(F("price") * F("quantity")),
            units=Sum("quantity"),
            orders=Count("order_id", distinct=True),
        )
        .order_by("day")
    )

    labels = [r["day"].strftime("%b %d") for r in qs if r["day"]]
    revenue = [float(r["revenue"] or 0) for r in qs]
    units = [int(r["units"] or 0) for r in qs]

    return JsonResponse({
        "labels": labels,
        "revenue": revenue,
        "units": units,
    })


# ---------------------------------------------------------------------------
# Org remittance (own org only — view ledger, not manage all orgs)
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_organization)
def org_remittance_view(request):
    """Active cycle(s) for the logged-in organization only."""
    org = _require_org(request.user)
    if not org:
        messages.error(request, "No organization linked to your account.")
        return redirect("organization.panel")

    ledgers = (
        OrganizationPlatformLedger.objects.filter(organization=org)
        .order_by("-cycle_start")
    )
    # Prefer open/due for "active" table; fall back to latest
    active = list(
        ledgers.filter(status__in=["OPEN", "DUE"]).order_by("-cycle_start")[:5]
    )
    if not active and ledgers.exists():
        active = [ledgers.first()]

    latest = ledgers.first()

    context = {
        **_sidebar_context(request.user),
        "org": org,
        "org_name": org.name,
        "ledgers": active,
        "latest": latest,
        "all_ledgers_count": ledgers.count(),
    }
    return render(
        request,
        "UTrade_app/organization/organization_panel/remittance.html",
        context,
    )


@login_required
@user_passes_test(is_organization)
def org_remittance_logs(request):
    """Paid remittances / receipts for this organization only."""
    org = _require_org(request.user)
    if not org:
        messages.error(request, "No organization linked to your account.")
        return redirect("organization.panel")

    paid_ledgers = (
        OrganizationPlatformLedger.objects.filter(
            organization=org,
            status="PAID",
        )
        .order_by("-updated_at", "-cycle_due")
    )

    remittances = (
        PlatformFeeRemittance.objects.filter(ledger__organization=org)
        .select_related("ledger", "ledger__organization", "recorded_by")
        .order_by("-payment_date", "-created_at")
    )

    context = {
        **_sidebar_context(request.user),
        "org": org,
        "org_name": org.name,
        "paid_ledgers": paid_ledgers[:50],
        "remittances": remittances[:50],
    }
    return render(
        request,
        "UTrade_app/organization/organization_panel/remittance_logs.html",
        context,
    )


@login_required
@user_passes_test(is_organization)
def org_view_remittance_receipt(request, ledger_id):
    """View receipt only if ledger belongs to this org."""
    org = _require_org(request.user)
    ledger = get_object_or_404(
        OrganizationPlatformLedger,
        id=ledger_id,
        organization=org,
        status="PAID",
    )
    # Reuse management receipt template if available, or simple page
    remittance = (
    PlatformFeeRemittance.objects.filter(
        ledger=ledger,
        ledger__organization=org,
    )
    .order_by("-id")
    .first()
    ) 
          
    context = {
        **_sidebar_context(request.user),
        "org": org,
        "ledger": ledger,
        "remittance": remittance,
    }
    return render(
        request,
        "UTrade_app/organization/organization_panel/remittance_receipt.html",
        context,
    )