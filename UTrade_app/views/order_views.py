import traceback
import requests
import base64
import json
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from django.contrib import messages

from ..models import (
    CartItem,
    Order,
    OrderItem,
    Review,
    ProductVariant,
    ChatMessage,
    Conversation,
    PreOrderRequest,
)


@login_required
@transaction.atomic
def place_order(request):
    if request.method != "POST":
        return redirect('cart_detail')

    payment_method = request.POST.get('payment_method')
    item_ids = request.POST.getlist('item_ids')

    if payment_method == "GCASH_ONLINE":
        payment_method = "GCASH"

    selected_items = CartItem.objects.filter(
        id__in=item_ids,
        cart__user=request.user,
    ).select_related('variant', 'variant__product')

    if not selected_items.exists():
        return redirect('cart_detail')

    try:
        with transaction.atomic():
            total_price = sum(item.get_cost() for item in selected_items)
            first_item = selected_items.first()
            product = first_item.variant.product
            order_seller = product.seller

            # Location from product listing
            location_text = (getattr(product, 'meetup_location_text', None) or '').strip()

            new_order = Order.objects.create(
                user=request.user,
                seller=order_seller,
                total_amount=total_price,
                payment_method=payment_method,
                pickup_location=location_text,
                meetup_location=location_text,
                buyer_note=request.POST.get('buyer_note') or '',
                status='Pending',
            )

            for item in selected_items:
                variant = item.variant
                if variant.stocks < item.quantity:
                    raise Exception(f"Not enough stock for {variant.product.name}")
                variant.stocks -= item.quantity
                variant.save(update_fields=['stocks'])

                OrderItem.objects.create(
                    order=new_order,
                    product_variant=variant,
                    price=variant.price,
                    quantity=item.quantity,
                )

        if payment_method == "GCASH":
            url = "https://api.paymongo.com/v1/checkout_sessions"
            secret_key = settings.PAYMONGO_SECRET_KEY
            encoded_key = base64.b64encode(f"{secret_key}:".encode()).decode()

            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": f"Basic {encoded_key}",
            }

            payload = {
                "data": {
                    "attributes": {
                        "line_items": [{
                            "currency": "PHP",
                            "amount": int(total_price * 100),
                            "name": f"UTrade Order #{new_order.id}",
                            "quantity": 1,
                        }],
                        "payment_method_types": ["gcash"],
                        "success_url": f"http://127.0.0.1:8000/order/success/{new_order.id}/",
                        "cancel_url": "http://127.0.0.1:8000/cart/",
                    }
                }
            }

            response = requests.post(url, json=payload, headers=headers)
            data = response.json()

            if "data" in data:
                checkout_url = data["data"]["attributes"]["checkout_url"]
                return redirect(checkout_url)

            print("PayMongo Error:", data)
            return redirect('cart_detail')

        return redirect('order_success', order_id=new_order.id)

    except Exception:
        print(traceback.format_exc())
        return redirect('cart_detail')


def submit_preorder_request(request, variant_id):
    if request.method == 'POST':
        try:
            variant = ProductVariant.objects.select_related('product', 'product__seller').get(id=variant_id)

            PreOrderRequest.objects.create(
                buyer=request.user,
                seller=variant.product.seller,
                product_variant=variant,
                status='PENDING',
                full_name_at_time=request.user.get_full_name(),
                student_no_at_time=getattr(request.user, 'student_no', '') or '',
                course_at_time=getattr(request.user, 'course', '') or '',
                section_at_time=getattr(request.user, 'section', '') or '',
            )

            return JsonResponse({'success': True, 'message': 'Request submitted'})

        except ProductVariant.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Variant not found'})

    return JsonResponse({'success': False, 'message': 'Invalid request'})


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.payment_method == "GCASH":
        order.status = "Paid"
        order.save(update_fields=['status'])

    CartItem.objects.filter(
        cart__user=request.user,
        variant__orderitem__order=order,
    ).delete()

    return render(request, 'UTrade_app/orders/success.html', {
        'order': order,
    })


@login_required
def order_history(request):
    orders = (
        Order.objects.filter(user=request.user)
        .select_related('seller')
        .prefetch_related(
            'items__product_variant__product',
            'items__product_variant__product__seller',
            'order_reviews',
        )
        .order_by('-created_at')
    )

    pending_orders = orders.filter(status__in=['Pending', 'Paid'])
    pickup_orders = orders.filter(status__in=['Accepted', 'Delivered'])

    completed = list(orders.filter(status='Completed'))
    cancelled = list(orders.filter(status='Cancelled'))

    # Unrated completed first, then rated completed, cancelled last
    needs_rating = [o for o in completed if not o.is_rated]
    already_rated = [o for o in completed if o.is_rated]
    history_orders = needs_rating + already_rated + cancelled

    preorders = (
        PreOrderRequest.objects.filter(buyer=request.user)
        .select_related(
            'seller',
            'product_variant',
            'product_variant__product',
            'product_variant__product__seller',
        )
        .order_by('-created_at')
    )
    preorder_pending = preorders.filter(status__in=['PENDING', 'APPROVED', 'PREPARING'])
    preorder_ready = preorders.filter(status='READY')

    context = {
        'orders': orders,
        'pending_orders': pending_orders,
        'pending_count': pending_orders.count(),
        'pickup_orders': pickup_orders,
        'pickup_count': pickup_orders.count(),
        'history_orders': history_orders,  # use this in History tab
        'completed_orders': completed,
        'completed_count': len(completed),
        'preorders': preorders,
        'preorder_pending_count': preorder_pending.count(),
        'preorder_ready_count': preorder_ready.count(),
    }
    return render(request, 'UTrade_app/orders/history.html', context)


@login_required
@transaction.atomic
def cancel_order(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)

        if order.status != 'Pending':
            return JsonResponse(
                {'status': 'error', 'message': 'Order cannot be cancelled.'},
                status=400,
            )

        for item in order.items.all():
            variant = item.product_variant
            if variant:
                variant.stocks += item.quantity
                variant.save(update_fields=['stocks'])

        reason = request.POST.get('reason', 'No reason provided')
        order.status = 'Cancelled'
        order.cancellation_reason = reason
        order.save(update_fields=['status', 'cancellation_reason'])

        first_item = order.items.first()
        product = first_item.product_variant.product if first_item and first_item.product_variant else None

        if product:
            conversation, _ = Conversation.objects.get_or_create(
                product=product,
                buyer=request.user,
                seller=order.seller,
            )
            ChatMessage.objects.create(
                conversation=conversation,
                user=request.user,
                content=(
                    f"🚨 SYSTEM: Order #{order.id} has been cancelled by the buyer.\n"
                    f"Reason: {reason}"
                ),
                is_read=False,
            )

        return JsonResponse({'status': 'success', 'message': 'Order cancelled successfully.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request.'}, status=400)


@login_required
def accept_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, seller=request.user)

    if request.method == "POST":
        order.seller_note = request.POST.get('seller_note', '')

        # If location was empty at place time, allow seller to set it on accept
        loc = (request.POST.get('pickup_location') or '').strip()
        if loc:
            order.pickup_location = loc
            order.meetup_location = loc
        elif not order.pickup_location:
            # fallback: first product's meetup text
            first = order.items.select_related(
                'product_variant__product'
            ).first()
            if first and first.product_variant and first.product_variant.product:
                text = (first.product_variant.product.meetup_location_text or '').strip()
                order.pickup_location = text
                order.meetup_location = text

        if order.status in ['Pending', 'Paid']:
            order.status = 'Accepted'
            order.save(update_fields=[
                'status',
                'seller_note',
                'pickup_location',
                'meetup_location',
            ])
            messages.success(request, f"Order #{order.id} has been accepted!")
        else:
            messages.warning(request, "This order cannot be accepted.")

    return redirect('seller_inventory')


@login_required
def mark_order_delivered(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, seller=request.user)

        if order.status != 'Accepted':
            messages.error(request, "Only accepted orders can be marked as completed.")
            return redirect('seller_inventory')

        order.status = 'Completed'
        order.save(update_fields=['status', 'updated_at'])

        for item in order.items.all():
            product = item.product_variant.product
            product.sold += item.quantity
            product.save(update_fields=['sold'])

        messages.success(request, f"Order #{order.id} has been marked as Completed.")

    return redirect('seller_inventory')


@login_required
def confirm_receipt(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)

        if order.status == 'Completed':
            messages.info(request, "This order is already completed. You can now rate the product.")
        elif order.status in ('Accepted', 'Delivered'):
            order.status = 'Completed'
            order.save(update_fields=['status', 'updated_at'])

            for item in order.items.all():
                product = item.product_variant.product
                product.sold += item.quantity
                product.save(update_fields=['sold'])

            messages.success(request, "Order completed! Please rate the product.")
        else:
            messages.error(request, "This order cannot be confirmed yet.")

    return redirect('order_history')


@login_required
def submit_review(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)

        if order.status != 'Completed':
            messages.error(request, "You can only rate completed orders.")
            return redirect('order_history')

        rating_value = request.POST.get('rating')
        comment = request.POST.get('comment')

        for item in order.items.all():
            Review.objects.update_or_create(
                order=order,
                product=item.product_variant.product,
                user=request.user,
                defaults={
                    'rating': rating_value,
                    'comment': comment,
                },
            )

        messages.success(request, "Thank you for your review!")
        return redirect('order_history')

    return redirect('order_history')


@login_required
@require_POST
def update_preorder_status(request, order_id):
    """Buyer actions on PreOrderRequest (cancel / complete)."""
    try:
        data = json.loads(request.body)
        new_status = (data.get('status') or '').upper()
        reason = (data.get('reason') or '').strip()

        po = get_object_or_404(PreOrderRequest, id=order_id, buyer=request.user)

        valid = {'PENDING', 'APPROVED', 'PREPARING', 'READY', 'COMPLETED', 'DECLINED'}
        if new_status not in valid:
            return JsonResponse({'success': False, 'message': 'Invalid status.'}, status=400)

        if new_status == 'DECLINED':
            if (po.status or '').upper() != 'PENDING':
                return JsonResponse(
                    {'success': False, 'message': 'Only pending pre-orders can be cancelled.'},
                    status=400,
                )
            if not reason:
                return JsonResponse(
                    {'success': False, 'message': 'Cancellation reason is required.'},
                    status=400,
                )
            po.status = 'DECLINED'
            if hasattr(po, 'cancellation_reason'):
                po.cancellation_reason = reason
                po.save(update_fields=['status', 'cancellation_reason'])
            else:
                po.save(update_fields=['status'])
            return JsonResponse({'success': True, 'message': 'Pre-order cancelled.'})

        if new_status == 'COMPLETED':
            if (po.status or '').upper() != 'READY':
                return JsonResponse(
                    {'success': False, 'message': 'Pre-order is not ready yet.'},
                    status=400,
                )
            po.status = 'COMPLETED'
            po.save(update_fields=['status'])
            return JsonResponse({'success': True, 'message': 'Pre-order completed.'})

        return JsonResponse({'success': False, 'message': 'Action not allowed.'}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def generate_receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    context = {
        'order': order,
        'items': order.items.select_related('product_variant', 'product_variant__product'),
        'buyer': request.user,
        'seller': order.seller,
        'is_preorder': False,
    }

    html_string = render_to_string('UTrade_app/reports/receipt_pdf.html', context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Receipt_Order_{order.id}.pdf"'
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    return response


@login_required
def generate_preorder_receipt(request, preorder_id):
    preorder = get_object_or_404(
        PreOrderRequest,
        id=preorder_id,
        buyer=request.user,
        status='COMPLETED',
    )

    context = {
        'order': preorder,
        'buyer': preorder.buyer,
        'is_preorder': True,
        'date': preorder.updated_at,
    }

    html_string = render_to_string('UTrade_app/reports/receipt_pdf.html', context)
    result = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="PreOrder_Receipt_{preorder.id}.pdf"'
    response.write(result)
    return response