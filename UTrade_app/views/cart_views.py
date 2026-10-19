import uuid
from collections import defaultdict
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Sum, F
from django.urls import reverse

from ..models import (
    Cart,
    CartItem,
    ProductVariant,
    MeetupLocation,
    Order,
    OrderItem,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _to_decimal(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _payment_flags(items):
    """Return (can_use_gcash, can_use_cop) for a list of CartItems."""
    methods = [i.variant.product.accepted_payments or "BOTH" for i in items]
    can_gcash = all(m in ("GCASH", "BOTH") for m in methods)
    can_cop = all(m in ("COP", "BOTH") for m in methods)
    return can_gcash, can_cop


def _parse_item_ids(raw_values):
    """Clean, de-duplicate (order preserved) and int-convert ids. Raises ValueError."""
    seen, clean = set(), []
    for x in raw_values:
        x = str(x).strip()
        if x and x not in seen:
            seen.add(x)
            clean.append(x)
    return [int(x) for x in clean]


def _collect_item_ids(request):
    """Read selected cart item ids from POST (item_ids / item_ids[]) or GET (?items=1,2,3)."""
    raw = request.POST.getlist("item_ids") or request.POST.getlist("item_ids[]")
    if not raw:
        single = (request.POST.get("item_ids") or request.GET.get("items") or "").strip()
        if single:
            raw = [x for x in single.split(",") if x.strip()]
    return _parse_item_ids(raw)


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
    # The cart's JS sends the selected ids either as ?items=1,2,3 (GET) or as a POST.
    # A POST is converted to a GET so the checkout page survives a refresh.
    if request.method == "POST":
        try:
            ids = _collect_item_ids(request)
        except ValueError:
            return redirect("cart_detail")
        if not ids:
            messages.warning(request, "No items selected for checkout.")
            return redirect("cart_detail")
        return redirect(f"{reverse('checkout_view')}?items={','.join(map(str, ids))}")

    item_ids_str = request.GET.get("items", "")

    base_qs = CartItem.objects.select_related(
        "variant",
        "variant__product",
        "variant__product__seller",
        "variant__assigned_image",
    ).prefetch_related("variant__product__images")

    if item_ids_str:
        try:
            item_ids = [int(x) for x in item_ids_str.split(",") if x.strip()]
        except ValueError:
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
    """
    try:
        item_ids = _collect_item_ids(request)
    except (TypeError, ValueError):
        messages.error(request, "Invalid cart items.")
        return redirect("cart_detail")

    if not item_ids:
        messages.error(request, "No items to order.")
        return redirect("cart_detail")

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
        messages.error(request, str(e))
        return redirect("cart_detail")
    except Exception as e:
        messages.error(request, f"Could not place order: {e}")
        return redirect("cart_detail")

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

    return redirect("order_list")