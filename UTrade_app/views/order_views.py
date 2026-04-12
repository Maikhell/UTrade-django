import traceback
import requests
import base64
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from ..models import CartItem, Order, OrderItem, Review
from django.db.models import Q
from django.contrib import messages

@login_required
def place_order(request):
    if request.method == "POST":
        payment_method = request.POST.get('payment_method')
        item_ids = request.POST.getlist('item_ids')
        
        if payment_method == "GCASH_ONLINE":
            payment_method = "GCASH"

        selected_items = CartItem.objects.filter(id__in=item_ids, cart__user=request.user)

        if not selected_items.exists():
            return redirect('cart_detail')

        try:
            with transaction.atomic():
                total_price = sum(item.get_cost() for item in selected_items)
                first_item = selected_items.first()
                order_seller = first_item.variant.product.seller

                # Create the order
                new_order = Order.objects.create(
                    user=request.user,
                    seller=order_seller, 
                    total_amount=total_price,
                    payment_method=payment_method, # Will save 'GCASH'
                    pickup_location=request.POST.get('pickup_location'),
                    buyer_note=request.POST.get('buyer_note'),         
                    status='Pending'
                )

                for item in selected_items:
                    OrderItem.objects.create(
                        order=new_order,
                        product_variant=item.variant,
                        price=item.variant.price,
                        quantity=item.quantity
                    )

            if payment_method == "GCASH":
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
                            "line_items": [{
                                "currency": "PHP",
                                "amount": int(total_price * 100),
                                "name": f"UTrade Order #{new_order.id}",
                                "quantity": 1
                            }],
                            "payment_method_types": ["gcash"],
                            "success_url": f"http://127.0.0.1:8000/order/success/{new_order.id}/",
                            "cancel_url": "http://127.0.0.1:8000/cart/"
                        }
                    }
                }

                response = requests.post(url, json=payload, headers=headers)
                data = response.json()

                if "data" in data:
                    checkout_url = data["data"]["attributes"]["checkout_url"]
                    return redirect(checkout_url)
                else:
                    print("PayMongo Error:", data)
                    return redirect('cart_detail')

            return redirect('order_success', order_id=new_order.id)

        except Exception as e:
            print(traceback.format_exc())
            return redirect('cart_detail')

    return redirect('cart_detail')



@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.payment_method == "GCASH":
        order.status = "Paid"
        order.save()
        
    CartItem.objects.filter(cart__user=request.user, variant__orderitem__order=order).delete()
    
    return render(request, 'UTrade_app/orders/order_success.html', {
        'order': order
    })
    
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    pickup_orders = orders.filter(
        Q(status='Accepted') | 
        Q(status='Delivered') |
        (Q(payment_method='GCASH') & Q(status='Paid'))
    )
    
    context = {
        'orders': orders,
        'pickup_orders': pickup_orders,
        'pickup_count': pickup_orders.count(),
    }
    return render(request, 'UTrade_app/orders/orders.html', {
        'orders': orders,
        'pickup_orders': pickup_orders,
        'pickup_count': pickup_orders.count(),
    })

@login_required
def accept_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, seller=request.user)

    if request.method == "POST":
        order.pickup_time = request.POST.get('pickup_time')
        order.meetup_location = request.POST.get('pickup_location')
        order.seller_note = request.POST.get('seller_note')

        if order.status in ['Pending', 'Paid']:
            order.status = 'Accepted' 
        
        order.save()
        
        messages.success(request, f"Order #{order.id} has been accepted!")
        return redirect('seller_inventory')

    return redirect('seller_inventory')

def mark_order_delivered(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, seller=request.user)
        
        order.status = 'Delivered'
        order.save()
        
        messages.success(request, f"Order #{order.id} marked as delivered! Waiting for buyer to confirm.")
        
    return redirect('seller_inventory') 

def confirm_receipt(request, order_id):
    if request.method == 'POST':
        # 1. Get the order and ensure the current user is the buyer
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        if order.status == 'Delivered':
            with transaction.atomic():
                order.status = 'Completed'
                order.save()
                
                for item in order.items.all():
                    variant = item.product_variant
                    product = variant.product
                    

                    variant.stocks -= item.quantity
                    variant.save()

                    product.sold += item.quantity 
                    product.save()
            
            messages.success(request, "Order completed! order has been transfered to order history please rate the product to help the community")
        else:
            messages.error(request, "This order cannot be confirmed yet.")
            
    return redirect('order_history')

def submit_review(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        if order.status != 'Completed':
            messages.error(request, "You can only rate completed orders.")
            return redirect('order_history')

        rating_value = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        items = order.items.all()
        
        for item in items:
            Review.objects.update_or_create(
                order=order,
                product=item.product_variant.product,
                user=request.user,
                defaults={
                    'rating': rating_value,
                    'comment': comment
                }
            )

        messages.success(request, "Thank you for your review!")
        return redirect('order_history')
    
    return redirect('order_history')