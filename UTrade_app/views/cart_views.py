import re
import uuid
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Sum, F
from django.urls import reverse
from django.utils import timezone

from ..models import (
    Cart,
    CartItem,
    ProductVariant,
    MeetupLocation,
    Order,
    OrderItem,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _to_decimal(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _checkout_url(item_ids):
    return f"{reverse('checkout_view')}?items={','.join(map(str, item_ids))}"


def _payment_flags(items):
    """Return (can_use_gcash, can_use_cop) for a list of CartItems."""
    methods = [
        (i.variant.product.accepted_payments or "BOTH").strip().upper()
        for i in items
    ]
    can_gcash = all(m in ("GCASH", "BOTH") for m in methods)
    can_cop = all(m in ("COP", "BOTH") for m in methods)
    return can_gcash, can_cop


def _dedupe(ids):
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _collect_item_ids(request):
    """
    Read selected cart item ids. NEVER raises: unreadable values are skipped.

    Sources, in priority order:
      1. POST item_ids / item_ids[]  (one hidden field per item). Every value is
         reduced to its digits, so a localized id such as "1,001" still reads 1001.
      2. POST items                  (comma-separated fallback)
      3. GET  items                  (?items=1,2,3)
    """
    raw = request.POST.getlist("item_ids") + request.POST.getlist("item_ids[]")
    ids = []
    for value in raw:
        digits = re.sub(r"\D", "", str(value))
        if digits:
            ids.append(int(digits))

    if not ids:
        csv = request.POST.get("items") or request.GET.get("items") or ""
        for token in csv.split(","):
            token = token.strip()
            if token.isdigit():
                ids.append(int(token))

    return _dedupe(ids)


# --------------------------------------------------------------------------- #
# Cart
# --------------------------------------------------------------------------- #
@login_required
def cart_detail(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    # Order by seller *id* (usernames are nullable / not unique) so {% regroup %} is reliable.
    cart_items = (
        cart.items.select_related(
            "variant",
            "variant__product",
            "variant__product__seller",
            "variant__assigned_image",
        )
        .prefetch_related("variant__product__images")
        .order_by("variant__product__seller_id", "-id")
    )

    total_price = sum((item.get_cost() for item in cart_items), Decimal("0.00"))

    return render(
        request,
        "UTrade_app/cart/details.html",
        {
            "cart": cart,
            "cart_items": cart_items,
            "total_price": total_price,
            "meetup_locations": MeetupLocation.objects.filter(is_active=True),
        },
    )


@login_required
@require_POST
def add_to_cart(request, variant_id):
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "message": "Please login first"}, status=401)

    variant = get_object_or_404(ProductVariant, id=variant_id)
    cart, _ = Cart.objects.get_or_create(user=request.user)

    cart_item, item_created = CartItem.objects.get_or_create(cart=cart, variant=variant)

    if not item_created:
        if cart_item.quantity < variant.stocks:
            cart_item.quantity += 1
            cart_item.save()
        else:
            return JsonResponse(
                {"success": False, "message": f"Only {variant.stocks} items available."},
                status=400,
            )

    total_quantity = (
        CartItem.objects.filter(cart=cart).aggregate(Sum("quantity"))["quantity__sum"] or 0
    )
    return JsonResponse({"success": True, "cart_count": total_quantity})


@login_required
@require_POST
def update_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    action = request.POST.get("action")

    if action == "up":
        if cart_item.quantity < cart_item.variant.stocks:
            cart_item.quantity += 1
        else:
            messages.warning(request, "Maximum stocks reached.")
    elif action == "down":
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
        else:
            cart_item.delete()
            return redirect("cart_detail")

    cart_item.save()
    return redirect("cart_detail")


@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    messages.info(request, "Item removed from cart.")
    return redirect("cart_detail")


# --------------------------------------------------------------------------- #
# Checkout
# --------------------------------------------------------------------------- #
def _group_cart_items_by_seller(cart_items):
    """
    Group CartItem list by product.seller_id.
    Returns list of dicts: seller, seller_name, items, subtotal, payment flags.
    """
    sellers_map = {}
    for item in cart_items:
        product = item.variant.product
        seller = product.seller
        if seller is None:
            continue
        sid = seller.pk
        if sid not in sellers_map:
            sellers_map[sid] = {
                "seller": seller,
                "seller_id": sid,
                "seller_name": (
                    seller.get_full_name()
                    or getattr(seller, "display_name", None)
                    or seller.username
                    or str(seller.student_no)
                ),
                "items": [],
                "subtotal": Decimal("0.00"),
            }
        sellers_map[sid]["items"].append(item)
        sellers_map[sid]["subtotal"] += _to_decimal(item.get_cost())

    seller_groups = []
    for g in sellers_map.values():
        g["can_use_gcash"], g["can_use_cop"] = _payment_flags(g["items"])
        g["has_payment_conflict"] = not (g["can_use_gcash"] or g["can_use_cop"])
        seller_groups.append(g)

    seller_groups.sort(key=lambda g: (g["seller_name"] or "").lower())
    return seller_groups


@login_required
def checkout_view(request):
    # The cart's JS sends the selected ids as ?items=1,2,3 (GET).
    # A POST is converted to a GET so the checkout page survives a refresh.
    if request.method == "POST":
        ids = _collect_item_ids(request)
        if not ids:
            messages.warning(request, "No items selected for checkout.")
            return redirect("cart_detail")
        return redirect(_checkout_url(ids))

    base_qs = CartItem.objects.select_related(
        "variant",
        "variant__product",
        "variant__product__seller",
        "variant__assigned_image",
    ).prefetch_related("variant__product__images")

    if request.GET.get("items"):
        item_ids = _collect_item_ids(request)
        if not item_ids:
            return redirect("cart_detail")
        cart_items = list(base_qs.filter(id__in=item_ids, cart__user=request.user))
    else:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_items = list(base_qs.filter(cart=cart))

    if not cart_items:
        messages.warning(request, "No items selected for checkout.")
        return redirect("cart_detail")

    seller_groups = _group_cart_items_by_seller(cart_items)
    if not seller_groups:
        messages.error(request, "Could not determine sellers for selected items.")
        return redirect("cart_detail")

    total_price = sum((g["subtotal"] for g in seller_groups), Decimal("0.00"))
    has_payment_conflict = any(g["has_payment_conflict"] for g in seller_groups)

    return render(
        request,
        "UTrade_app/cart/checkout.html",
        {
            "items": cart_items,
            "seller_groups": seller_groups,
            "total_price": total_price,
            "user": request.user,
            "has_payment_conflict": has_payment_conflict,
        },
    )


@login_required
@require_POST
def place_order(request):
    """
    Create ONE Order (with its own unique id / order_number) per product.seller_id.
    Each order gets only that seller's cart items and the matching total.
    Payment method is chosen per seller (payment_method_<seller_id>), falling back
    to a global `payment_method` field.

    On a failure this view sends the buyer back to the CHECKOUT page with a
    message (never silently to the cart), and logs the reason.
    """
    item_ids = _collect_item_ids(request)

    if not item_ids:
        logger.warning(
            "place_order: no item ids received for user %s. POST keys=%s",
            request.user.pk,
            sorted(request.POST.keys()),
        )
        messages.error(
            request,
            "We couldn't read which items you selected. Please review your order and try again.",
        )
        # No ?items= -> checkout_view loads the whole cart (or goes to the cart if it is empty).
        return redirect("checkout_view")

    created_orders = []
    batch_id = uuid.uuid4()

    try:
        with transaction.atomic():
            cart_items = list(
                CartItem.objects.filter(id__in=item_ids, cart__user=request.user)
                .select_related(
                    "variant",
                    "variant__product",
                    "variant__product__seller",
                )
            )

            if not cart_items:
                # Most common cause: the form was submitted twice (double click) and the
                # first request already placed the orders and emptied the cart lines.
                just_ordered = Order.objects.filter(
                    user=request.user,
                    created_at__gte=timezone.now() - timedelta(minutes=2),
                ).exists()
                logger.warning(
                    "place_order: ids %s not found in cart of user %s (just_ordered=%s)",
                    item_ids, request.user.pk, just_ordered,
                )
                if just_ordered:
                    messages.info(request, "Your order was already placed. See it below.")
                    return redirect("order_history")
                messages.error(request, "Selected items are no longer in your cart.")
                return redirect("cart_detail")

            # Lock the variant rows so stock can't be oversold by concurrent checkouts.
            locked_variants = {
                v.pk: v
                for v in ProductVariant.objects.select_for_update().filter(
                    pk__in={i.variant_id for i in cart_items}
                )
            }

            # ---- group strictly by product.seller_id ----
            by_seller = defaultdict(list)
            for item in cart_items:
                seller_id = item.variant.product.seller_id
                if not seller_id:
                    raise ValueError(
                        f"Product '{item.variant.product.name}' has no seller."
                    )
                by_seller[seller_id].append(item)

            # ---- one Order per seller ----
            for seller_id, items in by_seller.items():
                seller = items[0].variant.product.seller

                # payment method for THIS seller
                can_gcash, can_cop = _payment_flags(items)
                if not (can_gcash or can_cop):
                    raise ValueError(
                        f"Items from @{seller.username or seller.student_no} have "
                        f"conflicting payment methods."
                    )
                requested = (
                    request.POST.get(f"payment_method_{seller_id}")
                    or request.POST.get("payment_method")
                    or ""
                ).strip().upper()
                if requested not in ("GCASH", "COP"):
                    requested = "GCASH" if can_gcash else "COP"
                if (requested == "GCASH" and not can_gcash) or (
                    requested == "COP" and not can_cop
                ):
                    raise ValueError(
                        f"{requested} is not accepted for all items from "
                        f"@{seller.username or seller.student_no}."
                    )

                # stock + ownership checks (this seller only), against locked rows
                total = Decimal("0.00")
                lines = []
                for item in items:
                    variant = locked_variants.get(item.variant_id)
                    if variant is None:
                        raise ValueError(
                            f"{item.variant.product.name} is no longer available."
                        )
                    if item.quantity < 1 or item.quantity > variant.stocks:
                        raise ValueError(
                            f"Not enough stock for {item.variant.product.name} "
                            f"({variant.variant_name}). Available: {variant.stocks}."
                        )
                    if item.variant.product.seller_id != seller_id:
                        raise ValueError(
                            f"Seller mismatch for {item.variant.product.name}"
                        )
                    price = _to_decimal(variant.price)
                    total += price * item.quantity
                    lines.append((item, variant, price))

                order = Order.objects.create(
                    user=request.user,
                    seller=seller,
                    total_amount=total,
                    status="Pending",
                    payment_method=requested,
                    checkout_batch=batch_id,
                )

                for item, variant, price in lines:
                    OrderItem.objects.create(
                        order=order,
                        product_variant=variant,
                        quantity=item.quantity,
                        price=price,
                    )
                    ProductVariant.objects.filter(pk=variant.pk).update(
                        stocks=F("stocks") - item.quantity
                    )

                created_orders.append(order)

            # remove ordered cart lines only after ALL orders succeed
            CartItem.objects.filter(
                id__in=item_ids,
                cart__user=request.user,
            ).delete()

    except ValueError as e:
        # Business-rule problems (stock, payment mismatch, ...) are safe to show.
        logger.info("place_order rejected for user %s: %s", request.user.pk, e)
        messages.error(request, str(e))
        return redirect(_checkout_url(item_ids))
    except Exception:
        # Unexpected errors (e.g. DB / migration problems): log the traceback,
        # show a generic message instead of leaking internals to the buyer.
        logger.exception("place_order failed for user %s, items %s", request.user.pk, item_ids)
        messages.error(
            request,
            "Something went wrong while placing your order. Nothing was charged or removed "
            "from your cart. Please try again.",
        )
        return redirect(_checkout_url(item_ids))

    def _label(o):
        return o.order_number or f"#{o.id}"

    if len(created_orders) == 1:
        o = created_orders[0]
        messages.success(
            request,
            f"Order {_label(o)} placed with @{o.seller.username or o.seller.student_no} "
            f"(₱{o.total_amount}).",
        )
    else:
        summary = ", ".join(
            f"{_label(o)}→@{o.seller.username or o.seller.student_no} (₱{o.total_amount})"
            for o in created_orders
        )
        messages.success(
            request,
            f"{len(created_orders)} separate orders created: {summary}",
        )

    return redirect("order_history")