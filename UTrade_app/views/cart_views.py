from collections import defaultdict
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Sum, F

from ..models import (
    Cart,
    CartItem,
    ProductVariant,
    MeetupLocation,
    Order,
    OrderItem,
)


@login_required
def cart_detail(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    cart_items = (
        cart.items.select_related(
            "variant",
            "variant__product",
            "variant__product__seller",
            "variant__assigned_image",
        )
        .prefetch_related("variant__product__images")
        .order_by("variant__product__seller__username", "-id")
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
                "seller_name": (
                    seller.get_full_name()
                    or getattr(seller, "display_name", None)
                    or seller.username
                ),
                "items": [],
                "subtotal": Decimal("0.00"),
                "payment_methods": set(),
            }
        cost = item.get_cost()
        if not isinstance(cost, Decimal):
            cost = Decimal(str(cost))
        sellers_map[sid]["items"].append(item)
        sellers_map[sid]["subtotal"] += cost
        sellers_map[sid]["payment_methods"].add(
            product.accepted_payments or "BOTH"
        )

    seller_groups = []
    for g in sellers_map.values():
        methods = g["payment_methods"]
        g["can_use_gcash"] = all(m in ("GCASH", "BOTH") for m in methods)
        g["can_use_cop"] = all(m in ("COP", "BOTH") for m in methods)
        g["has_payment_conflict"] = not (g["can_use_gcash"] or g["can_use_cop"])
        seller_groups.append(g)

    # Stable order by seller name
    seller_groups.sort(key=lambda g: (g["seller_name"] or "").lower())
    return seller_groups


@login_required
def checkout_view(request):
    item_ids_str = request.GET.get("items", "")

    if item_ids_str:
        try:
            item_ids = [int(x) for x in item_ids_str.split(",") if x.strip()]
        except ValueError:
            return redirect("cart_detail")
        cart_items = list(
            CartItem.objects.filter(id__in=item_ids, cart__user=request.user)
            .select_related(
                "variant",
                "variant__product",
                "variant__product__seller",
                "variant__assigned_image",
            )
            .prefetch_related("variant__product__images")
        )
    else:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_items = list(
            cart.items.select_related(
                "variant",
                "variant__product",
                "variant__product__seller",
                "variant__assigned_image",
            ).prefetch_related("variant__product__images")
        )

    if not cart_items:
        messages.warning(request, "No items selected for checkout.")
        return redirect("cart_detail")

    seller_groups = _group_cart_items_by_seller(cart_items)
    if not seller_groups:
        messages.error(request, "Could not determine sellers for selected items.")
        return redirect("cart_detail")

    total_price = sum((g["subtotal"] for g in seller_groups), Decimal("0.00"))
    all_methods = [
        item.variant.product.accepted_payments or "BOTH" for item in cart_items
    ]
    can_use_gcash = all(m in ("GCASH", "BOTH") for m in all_methods)
    can_use_cop = all(m in ("COP", "BOTH") for m in all_methods)

    return render(
        request,
        "UTrade_app/cart/checkout.html",
        {
            "items": cart_items,
            "seller_groups": seller_groups,
            "total_price": total_price,
            "user": request.user,
            "can_use_gcash": can_use_gcash,
            "can_use_cop": can_use_cop,
        },
    )


@login_required
@require_POST
def place_order(request):
    """
    Always create ONE Order per product.seller_id.
    Items / total_amount on each order belong only to that seller.
    """
    raw_ids = request.POST.getlist("item_ids")
    if not raw_ids:
        single = (request.POST.get("item_ids") or "").strip()
        if single:
            raw_ids = [x.strip() for x in single.split(",") if x.strip()]

    # De-duplicate while preserving order
    seen = set()
    clean_ids = []
    for x in raw_ids:
        x = str(x).strip()
        if not x or x in seen:
            continue
        seen.add(x)
        clean_ids.append(x)

    if not clean_ids:
        messages.error(request, "No items to order.")
        return redirect("cart_detail")

    try:
        item_ids = [int(x) for x in clean_ids]
    except (TypeError, ValueError):
        messages.error(request, "Invalid cart items.")
        return redirect("cart_detail")

    payment_method = (request.POST.get("payment_method") or "COP").strip().upper()
    if payment_method not in ("GCASH", "COP"):
        payment_method = "COP"

    cart_items = list(
        CartItem.objects.filter(id__in=item_ids, cart__user=request.user)
        .select_related(
            "variant",
            "variant__product",
            "variant__product__seller",
        )
        .select_for_update()  # lock rows during stock check (inside atomic below)
    )

    if not cart_items:
        messages.error(request, "Selected items are no longer in your cart.")
        return redirect("cart_detail")

    # Strict group by the product's seller user id
    by_seller_id = defaultdict(list)
    for item in cart_items:
        seller_id = item.variant.product.seller_id
        if not seller_id:
            messages.error(
                request,
                f"Product '{item.variant.product.name}' has no seller assigned.",
            )
            return redirect("cart_detail")
        by_seller_id[seller_id].append(item)

    created_orders = []

    try:
        with transaction.atomic():
            # Re-fetch with lock inside the transaction
            cart_items = list(
                CartItem.objects.filter(id__in=item_ids, cart__user=request.user)
                .select_related(
                    "variant",
                    "variant__product",
                    "variant__product__seller",
                )
                .select_for_update()
            )
            by_seller_id = defaultdict(list)
            for item in cart_items:
                by_seller_id[item.variant.product.seller_id].append(item)

            for seller_id, items in by_seller_id.items():
                if not items:
                    continue

                # Stock + ownership checks for THIS seller only
                for item in items:
                    variant = item.variant
                    if item.quantity > variant.stocks:
                        raise ValueError(
                            f"Not enough stock for {variant.product.name} "
                            f"({variant.variant_name}). Available: {variant.stocks}."
                        )
                    if variant.product.seller_id != seller_id:
                        raise ValueError(
                            f"Seller mismatch for {variant.product.name}"
                        )

                seller = items[0].variant.product.seller
                # Subtotal = ONLY this seller's items
                total = Decimal("0.00")
                for i in items:
                    cost = i.get_cost()
                    if not isinstance(cost, Decimal):
                        cost = Decimal(str(cost))
                    total += cost

                order = Order.objects.create(
                    user=request.user,
                    seller=seller,
                    total_amount=total,
                    status="Pending",
                    payment_method=payment_method,
                )

                for item in items:
                    OrderItem.objects.create(
                        order=order,
                        product_variant=item.variant,
                        quantity=item.quantity,
                        price=item.variant.price,
                    )
                    # Deduct stock for this line only
                    ProductVariant.objects.filter(pk=item.variant_id).update(
                        stocks=F("stocks") - item.quantity
                    )

                created_orders.append(order)

            # Remove ordered cart lines only after all orders succeed
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

    if len(created_orders) == 1:
        messages.success(
            request,
            f"Order #{created_orders[0].id} placed with @{created_orders[0].seller.username}.",
        )
    else:
        summary = ", ".join(
            f"#{o.id} → @{o.seller.username} (₱{o.total_amount})"
            for o in created_orders
        )
        messages.success(
            request,
            f"{len(created_orders)} separate orders created: {summary}",
        )

    return redirect("order_list")