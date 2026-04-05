import traceback
import requests
import base64
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from ..models import CartItem, Order, OrderItem
from django.db.models import Q

@login_required
def place_order(request):
    if request.method == "POST":
        print("STEP 1: POST received")

        payment_method = request.POST.get('payment_method')
        item_ids = request.POST.getlist('item_ids')

        print("ITEM IDS:", item_ids)

        # Define Selected Items
        selected_items = CartItem.objects.filter(
            id__in=item_ids,
            cart__user=request.user
        )

        print("SELECTED ITEMS COUNT:", selected_items.count())

        if not selected_items.exists():
            print("No selected items")
            return redirect('cart_detail')

        try:
            with transaction.atomic():
                # Calculate total
                total_price = sum(item.get_cost() for item in selected_items)
                print("TOTAL PRICE:", total_price)

                # Create Order
                new_order = Order.objects.create(
                    user=request.user,
                    total_amount=total_price,
                    payment_method=payment_method,
                    status='Pending'
                )

                print("ORDER CREATED:", new_order.id)

                # Create Order Items
                for item in selected_items:
                    OrderItem.objects.create(
                        order=new_order,
                        product_variant=item.variant,
                        price=item.variant.price,
                        quantity=item.quantity
                    )

            if payment_method == "GCASH_ONLINE":
                print("Initiating PayMongo Checkout")

                url = "https://api.paymongo.com/v1/checkout_sessions"

                secret_key = settings.PAYMONGO_SECRET_KEY
                encoded_key = base64.b64encode(f"{secret_key}:".encode()).decode()

                headers = {
                    "accept": "application/json",
                    "content-type": "application/json",
                    "authorization": f"Basic {encoded_key}"
                }

                payload = {
                    "data": {
                        "attributes": {
                            "line_items": [
                                {
                                    "currency": "PHP",
                                    "amount": int(total_price * 100),
                                    "name": f"UTrade Order #{new_order.id}",
                                    "quantity": 1
                                }
                            ],
                            "payment_method_types": ["gcash"],
                            "success_url": f"http://127.0.0.1:8000/order/success/{new_order.id}/",
                            "cancel_url": "http://127.0.0.1:8000/cart/"
                        }
                    }
                }

                response = requests.post(url, json=payload, headers=headers)
                data = response.json()

                print("PAYMONGO RESPONSE:", data)

                if "data" not in data:
                    print("PayMongo error:", data)
                    return redirect('cart_detail')

                checkout_url = data["data"]["attributes"]["checkout_url"]

                print("REDIRECTING TO:", checkout_url)

                return redirect(checkout_url)

            return redirect('order_success', order_id=new_order.id)

        except Exception as e:
            print("\n--- PAYMONGO / ORDER ERROR ---")
            print(traceback.format_exc())
            return redirect('cart_detail')

    return redirect('cart_detail')


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.payment_method == "GCASH_ONLINE":
        order.status = "Paid"
        order.save()
        CartItem.objects.filter(cart__user=request.user).delete()

    return render(request, 'UTrade_app/orders/order_success.html', {
        'order': order
    })
    
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    pickup_orders = orders.filter(
        Q(payment_method='GCASH', status='Paid') | 
        Q(payment_method='COP', status='Pending')
    )
    
    context = {
        'orders': orders,
        'pickup_orders': pickup_orders,
        'pickup_count': pickup_orders.count(),
    }
    return render(request, 'UTrade_app/orders/orders.html', context)