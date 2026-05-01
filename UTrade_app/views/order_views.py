import traceback
import requests
import base64
import json
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML

from ..models import CartItem, Order, OrderItem, Review, ProductVariant, ChatMessage, Conversation,PreOrderRequest
from django.db.models import Q
from django.http import JsonResponse
from django.contrib import messages

@login_required
@transaction.atomic
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
                    status='Pending '
                )
                for item in selected_items:
                    variant = item.variant
                    if variant.stocks >= item.quantity:
                        variant.stocks -= item.quantity
                        variant.save()
                    else:
                        raise Exception(f"Not enough stock for {variant.product.name}")
                    
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

def submit_preorder_request(request, variant_id): # Add variant_id here
    if request.method == 'POST':
        try:
            # We get variant_id from the URL parameter now, not the JSON body
            variant = ProductVariant.objects.get(id=variant_id)
            
            # Create the request record
            PreOrderRequest.objects.create(
                buyer=request.user,
                seller=variant.product.seller,
                product_variant=variant,
                status='PENDING', 
                full_name_at_time=request.user.get_full_name(), # Added this
                student_no_at_time=request.user.student_no,
                course_at_time=request.user.course,
                section_at_time=request.user.section
            )
            
            return JsonResponse({'success': True, 'message': 'Request submitted'}) # Changed 'status' to 'success' to match your JS
            
        except ProductVariant.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Variant not found'})

    return JsonResponse({'success': False, 'message': 'Invalid request'})
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
    
    pending_orders = orders.filter(status='Pending')
    
    pickup_orders = orders.filter(
        Q(status='Accepted') | 
        Q(status='Delivered') |
        (Q(payment_method='GCASH') & Q(status='Paid'))
    )

    preorders = PreOrderRequest.objects.filter(buyer=request.user).order_by('-created_at')

    # Pre-orders that are still in the 'processing' phase
    preorder_pending = preorders.filter(
        status__in=['PENDING', 'APPROVED', 'PREPARING']
    )

    # Pre-orders that are ready for the buyer to collect
    preorder_ready = preorders.filter(status='READY')

    context = {
        # Regular Orders
        'orders': orders,
        'pending_orders': pending_orders,
        'pending_count': pending_orders.count(),
        'pickup_orders': pickup_orders,
        'pickup_count': pickup_orders.count(),

        # Pre-Orders
        'preorders': preorders,
        'preorder_pending_count': preorder_pending.count(),
        'preorder_ready_count': preorder_ready.count(),
    }
    
    return render(request, 'UTrade_app/orders/orders.html', context)

@login_required
@transaction.atomic 
def cancel_order(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        if order.status != 'Pending':
            return JsonResponse({'status': 'error', 'message': 'Order cannot be cancelled.'}, status=400)
        
        for item in order.items.all():
            variant = item.product_variant
            variant.stocks += item.quantity
            variant.save()
            
        reason = request.POST.get('reason', 'No reason provided')
        order.status = 'Cancelled'
        order.cancellation_reason = reason 
        order.save()
        
        first_item = order.items.first()
        product = first_item.product_variant.product if first_item else None
        
        if product:

            conversation, created = Conversation.objects.get_or_create(
                product=product,
                buyer=request.user,
                seller=order.seller
            )

            notification_text = f"🚨 SYSTEM: Order #{order.id} has been cancelled by the buyer.\nReason: {reason}"
            
            ChatMessage.objects.create(
                conversation=conversation,
                user=request.user,
                content=notification_text,
                is_read=False
            )
        
        return JsonResponse({'status': 'success', 'message': 'Order cancelled successfully.'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request.'}, status=400)
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

def update_preorder_status(request, order_id):
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        
        order = get_object_or_404(Order, id=order_id)
        
        valid_statuses = ['PENDING', 'APPROVED', 'PREPARING', 'READY', 'COMPLETED', 'DECLINED']
        
        if new_status in valid_statuses:
            order.status = new_status
            order.save()
            return JsonResponse({
                'success': True, 
                'message': f'Order status updated to {new_status}'
            })
        else:
            return JsonResponse({
                'success': False, 
                'message': 'Invalid status provided'
            }, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
    
def generate_receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    context = {
        'order': order,
        'items': order.items.all(),
        'buyer': request.user,
        'seller': order.seller,
    }

    html_string = render_to_string('UTrade_app/orders/receipt_pdf.html', context)

    # Create PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Receipt_Order_{order.id}.pdf"'

    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)

    return response
def generate_preorder_receipt(request, preorder_id):
    preorder = get_object_or_404(PreOrderRequest, id=preorder_id, buyer=request.user, status='COMPLETED')
    
    context = {
        'order': preorder,  
        'buyer': preorder.buyer,
        'is_preorder': True,
        'date': preorder.updated_at, 
    }
    
    html_string = render_to_string('UTrade_app/orders/receipt_pdf.html', context)
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    result = html.write_pdf()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="PreOrder_Receipt_{preorder.id}.pdf"'
    response.write(result)
    return response