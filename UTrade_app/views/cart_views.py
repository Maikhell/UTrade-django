import base64
import re
import uuid
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Sum, F
from django.urls import reverse
from django.utils import timezone
from ..product_access import blocked_cart_reason, purchase_block_reason, resolve_size
from ..preorder_utils import cart_block_reasons, preorder_block_reason

import requests

from ..models import (
    Cart,
    CartItem,
    ProductVariant,
    MeetupLocation,
    Order,
    OrderItem,
    PreOrderRequest,
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


def _create_paymongo_session(request, payables, success_url):
    """
    One PayMongo GCash checkout session covering every GCash payment of a checkout.
    `payables` = [{"name": str, "amount": Decimal}, ...]. Returns the hosted URL, or None.
    """
    try:
        encoded_key = base64.b64encode(f"{settings.PAYMONGO_SECRET_KEY}:".encode()).decode()
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Basic {encoded_key}",
        }
        payload = {
            "data": {
                "attributes": {
                    "line_items": [
                        {
                            "currency": "PHP",
                            "amount": int((p["amount"] * 100).to_integral_value()),
                            "name": p["name"],
                            "quantity": 1,
                        }
                        for p in payables
                    ],
                    "payment_method_types": ["gcash"],
                    "success_url": success_url,
                    "cancel_url": request.build_absolute_uri(reverse("order_history")),
                }
            }
        }
        resp = requests.post(
            "https://api.paymongo.com/v1/checkout_sessions",
            json=payload, headers=headers, timeout=20,
        )
        data = resp.json()
        return data["data"]["attributes"]["checkout_url"]
    except Exception:
        logger.exception("PayMongo session failed for %s", [p["name"] for p in payables])
        return None


# --------------------------------------------------------------------------- #
# Cart
# --------------------------------------------------------------------------- #
@login_required
def cart_detail(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    # Order by seller *id* (usernames are nullable / not unique) so {% regroup %} is reliable.
    # Regular items come first, pre-order items after them, inside each seller.
    cart_items = (
        cart.items.select_related(
            "variant",
            "variant__product",
            "variant__product__seller",
            "variant__assigned_image",
        )
        .prefetch_related("variant__product__images")
        .order_by("variant__product__seller_id", "variant__product__pre_order", "-id")
    )

    # Evaluating the queryset caches the same objects the template iterates over.
    items = list(cart_items)
    reasons = cart_block_reasons(items)
    for item in items:
        item.pre_block = reasons.get(item.id)

    total_price = sum((item.get_cost() for item in items if not item.pre_block), Decimal("0.00"))

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

    variant = get_object_or_404(
        ProductVariant.objects.select_related(
            "product__seller__org_link",
            "product__related_org",
        ),
        id=variant_id,
    )

    # Private listings: only students of the organization's program can buy them
    reason = purchase_block_reason(request.user, variant.product)
    if reason:
        return JsonResponse({"success": False, "message": reason}, status=403)

    size, size_error = resolve_size(variant, request.POST.get("size"))
    if size_error:
        return JsonResponse({"success": False, "message": size_error}, status=400)

    cart, _ = Cart.objects.get_or_create(user=request.user)

    if variant.product.pre_order:
        # Pre-order: the period must be open and a slot must be left
        in_cart = (
            CartItem.objects.filter(cart=cart, variant=variant).aggregate(q=Sum("quantity"))["q"] or 0
        )
        block = preorder_block_reason(variant.product, variant, 1, in_cart)
        if block:
            return JsonResponse({"success": False, "message": block}, status=400)
        cart_item, item_created = CartItem.objects.get_or_create(cart=cart, variant=variant, size=size)
        if not item_created:
            cart_item.quantity += 1
            cart_item.save()
    else:
        cart_item, item_created = CartItem.objects.get_or_create(cart=cart, variant=variant, size=size)

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
        variant = cart_item.variant
        if variant.product.pre_order:
            in_cart = (
                CartItem.objects.filter(cart=cart_item.cart, variant=variant)
                .aggregate(q=Sum("quantity"))["q"] or 0
            )
            block = preorder_block_reason(variant.product, variant, 1, in_cart)
            if block:
                messages.warning(request, block)
            else:
                cart_item.quantity += 1
        elif cart_item.quantity < variant.stocks:
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
    Returns list of dicts: seller, seller_name, items (all), regular_items,
    preorder_items, subtotal, payment flags.
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
                "regular_items": [],
                "preorder_items": [],
                "subtotal": Decimal("0.00"),
            }
        group = sellers_map[sid]
        group["items"].append(item)
        (group["preorder_items"] if product.pre_order else group["regular_items"]).append(item)
        group["subtotal"] += _to_decimal(item.get_cost())

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
        "variant__product__seller__org_link",
        "variant__product__related_org",
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

    # Private listings: stop before the payment step if the buyer's program doesn't match
    blocked = blocked_cart_reason(request.user, cart_items)
    if blocked:
        messages.error(request, blocked)
        return redirect("cart_detail")

    # Pre-orders: the period must be open and the slots left must cover the cart
    pre_reasons = cart_block_reasons(cart_items)
    if pre_reasons:
        messages.error(request, next(iter(pre_reasons.values())))
        return redirect("cart_detail")

    seller_groups = _group_cart_items_by_seller(cart_items)
    if not seller_groups:
        messages.error(request, "Could not determine sellers for selected items.")
        return redirect("cart_detail")

    total_price = sum((g["subtotal"] for g in seller_groups), Decimal("0.00"))
    has_payment_conflict = any(g["has_payment_conflict"] for g in seller_groups)
    has_preorder = any(g["preorder_items"] for g in seller_groups)

    return render(
        request,
        "UTrade_app/cart/checkout.html",
        {
            "items": cart_items,
            "seller_groups": seller_groups,
            "total_price": total_price,
            "user": request.user,
            "has_payment_conflict": has_payment_conflict,
            "has_preorder": has_preorder,
        },
    )


@login_required
@require_POST
def place_order(request):
    """
    One regular Order per seller (own id / order_number) for the regular items,
    and one PreOrderRequest per pre-order cart line. Payment method is chosen per
    seller (payment_method_<seller_id>), falling back to a global `payment_method`.

    Pre-order lines are checked here against the pre-order period and the slots left
    (on rows locked for this checkout), and only then turned into seller records.

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
    created_preorders = []
    batch_id = uuid.uuid4()

    try:
        with transaction.atomic():
            cart_items = list(
                CartItem.objects.filter(id__in=item_ids, cart__user=request.user)
                .select_related(
                    "variant",
                    "variant__product",
                    "variant__product__seller",
                    "variant__product__seller__org_link",
                    "variant__product__related_org",
                )
            )

            if not cart_items:
                # Most common cause: the form was submitted twice (double click) and the
                # first request already placed the orders and emptied the cart lines.
                just_ordered = (
                    Order.objects.filter(
                        user=request.user,
                        created_at__gte=timezone.now() - timedelta(minutes=2),
                    ).exists()
                    or PreOrderRequest.objects.filter(
                        buyer=request.user,
                        created_at__gte=timezone.now() - timedelta(minutes=2),
                    ).exists()
                )
                logger.warning(
                    "place_order: ids %s not found in cart of user %s (just_ordered=%s)",
                    item_ids, request.user.pk, just_ordered,
                )
                if just_ordered:
                    messages.info(request, "Your order was already placed. See it below.")
                    return redirect("order_history")
                messages.error(request, "Selected items are no longer in your cart.")
                return redirect("cart_detail")

            # Private listings: only students of the organization's program can buy them.
            # Nothing has been created or locked yet, so this is a clean stop.
            blocked = blocked_cart_reason(request.user, cart_items)
            if blocked:
                logger.info("place_order blocked for user %s: %s", request.user.pk, blocked)
                messages.error(request, blocked)
                return redirect("cart_detail")

            # Lock the variant rows so stock / pre-order slots can't be oversold.
            locked_variants = {
                v.pk: v
                for v in ProductVariant.objects.select_for_update().filter(
                    pk__in={i.variant_id for i in cart_items}
                )
            }

            # ---- pre-orders: period + remaining slots, against the locked rows ----
            wanted = defaultdict(int)
            pre_products = {}
            for it in cart_items:
                if it.variant.product.pre_order:
                    wanted[it.variant_id] += it.quantity
                    pre_products[it.variant_id] = it.variant.product
            for variant_id, qty in wanted.items():
                locked = locked_variants.get(variant_id)
                if locked is None:
                    raise ValueError("A pre-order item is no longer available.")
                reason = preorder_block_reason(pre_products[variant_id], locked, qty)
                if reason:
                    raise ValueError(reason)

            # ---- group strictly by product.seller_id ----
            by_seller = defaultdict(list)
            for item in cart_items:
                seller_id = item.variant.product.seller_id
                if not seller_id:
                    raise ValueError(
                        f"Product '{item.variant.product.name}' has no seller."
                    )
                by_seller[seller_id].append(item)

            buyer = request.user

            for seller_id, items in by_seller.items():
                seller = items[0].variant.product.seller

                # payment method for THIS seller (covers its order and its pre-orders)
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

                regular_items = [i for i in items if not i.variant.product.pre_order]
                preorder_items = [i for i in items if i.variant.product.pre_order]

                # ---------- regular order (unchanged) ----------
                if regular_items:
                    total = Decimal("0.00")
                    lines = []
                    for item in regular_items:
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

                    location_text = (
                        getattr(regular_items[0].variant.product, "meetup_location_text", "") or ""
                    ).strip()
                    order = Order.objects.create(
                        user=buyer,
                        seller=seller,
                        total_amount=total,
                        status="Pending",
                        payment_method=requested,
                        checkout_batch=batch_id,
                        pickup_location=location_text,
                        meetup_location=location_text,
                        buyer_note=(request.POST.get("buyer_note") or "").strip(),
                    )

                    for item, variant, price in lines:
                        OrderItem.objects.create(
                            order=order,
                            product_variant=variant,
                            quantity=item.quantity,
                            price=price,
                            size=item.size,
                        )
                        ProductVariant.objects.filter(pk=variant.pk).update(
                            stocks=F("stocks") - item.quantity
                        )

                    created_orders.append(order)

                # ---------- pre-orders: the seller's records are created only now ----------
                for item in preorder_items:
                    variant = locked_variants[item.variant_id]
                    if item.quantity < 1:
                        raise ValueError(f"Invalid quantity for {item.variant.product.name}.")
                    po = PreOrderRequest.objects.create(
                        buyer=buyer,
                        seller=seller,
                        product_variant=variant,
                        quantity=item.quantity,
                        size=item.size,
                        status="PENDING",
                        payment_method=requested,
                        is_paid=False,
                        checkout_batch=batch_id,
                        full_name_at_time=buyer.get_full_name() or buyer.username or "",
                        student_no_at_time=getattr(buyer, "student_no", "") or "",
                        course_at_time=getattr(buyer, "course", "") or "",
                        section_at_time=getattr(buyer, "section", "") or "",
                    )
                    # limited variations: take the slots (no-limit variations are never reduced)
                    if variant.preorder_limit is not None:
                        ProductVariant.objects.filter(pk=variant.pk).update(
                            stocks=F("stocks") - item.quantity
                        )
                    po.line_total = _to_decimal(variant.price) * item.quantity
                    po.seller_label = seller.username or str(seller.student_no)
                    created_preorders.append(po)

            # remove ordered cart lines only after ALL orders succeed
            CartItem.objects.filter(
                id__in=item_ids,
                cart__user=request.user,
            ).delete()

    except ValueError as e:
        # Business-rule problems (stock, slots, period, payment mismatch...) are safe to show.
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
    elif created_orders:
        summary = ", ".join(
            f"{_label(o)}→@{o.seller.username or o.seller.student_no} (₱{o.total_amount})"
            for o in created_orders
        )
        messages.success(
            request,
            f"{len(created_orders)} separate orders created: {summary}",
        )

    if created_preorders:
        n = len(created_preorders)
        s = len({po.seller_id for po in created_preorders})
        messages.success(
            request,
            f"{n} pre-order{'s' if n != 1 else ''} sent to {s} seller{'s' if s != 1 else ''}. "
            f"You'll be notified when they respond.",
        )

    # GCash: send the buyer to PayMongo once for everything paid online.
    gcash_orders = [o for o in created_orders if o.payment_method == "GCASH"]
    gcash_preorders = [po for po in created_preorders if po.payment_method == "GCASH"]
    if gcash_orders or gcash_preorders:
        payables = [
            {"name": f"UTrade Order {_label(o)}", "amount": o.total_amount} for o in gcash_orders
        ]
        if gcash_preorders:
            totals, labels = defaultdict(Decimal), {}
            for po in gcash_preorders:
                totals[po.seller_id] += po.line_total
                labels[po.seller_id] = po.seller_label
            for sid, amount in totals.items():
                payables.append({"name": f"UTrade Pre-Order @{labels[sid]}", "amount": amount})
            # pre-orders have no Order to return to, so use the batch return page
            success_url = request.build_absolute_uri(reverse("checkout_success", args=[batch_id]))
        else:
            success_url = request.build_absolute_uri(
                reverse("order_success", args=[gcash_orders[0].id])
            )

        checkout_url = _create_paymongo_session(request, payables, success_url)
        if checkout_url:
            return redirect(checkout_url)
        messages.warning(
            request,
            "Your order was placed, but we couldn't start the GCash payment. "
            "Please contact the seller or try again later.",
        )

    return redirect("order_history")


@login_required
def checkout_success(request, batch):
    """PayMongo return page for checkouts that include pre-orders: marks the whole batch paid."""
    orders = Order.objects.filter(user=request.user, checkout_batch=batch)
    orders.filter(payment_method="GCASH", status="Pending").update(status="Paid")
    PreOrderRequest.objects.filter(
        buyer=request.user, checkout_batch=batch, payment_method="GCASH"
    ).update(is_paid=True)

    first = orders.order_by("id").first()
    if first:
        return render(request, "UTrade_app/orders/success.html", {"order": first})
    messages.success(request, "Payment received. Your pre-orders were sent to the sellers.")
    return redirect("order_history")