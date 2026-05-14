from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from ..models import Product, Cart, CartItem, ProductVariant, MeetupLocation
from django.db.models import Sum

@login_required
def cart_detail(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.items.all()
    
    total_price = sum(item.variant.price * item.quantity for item in cart_items)
    
    return render(request, 'UTrade_app/cart/details.html', {
        'cart': cart,
        'cart_items': cart_items,
        'total_price': total_price
    })
@login_required
@require_POST
def add_to_cart(request, variant_id):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Please login first'}, status=401)

    variant = get_object_or_404(ProductVariant, id=variant_id)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    
    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart, 
        variant=variant
    )
    
    if not item_created:
        if cart_item.quantity < variant.stocks:
            cart_item.quantity += 1
            cart_item.save()
        else:
            return JsonResponse({
                'success': False, 
                'message': f'Only {variant.stocks} items available.'
            }, status=400)
    
    total_quantity = CartItem.objects.filter(cart=cart).aggregate(Sum('quantity'))['quantity__sum'] or 0    
    
    return JsonResponse({
        'success': True,
        'cart_count': total_quantity,    
    })
@login_required
@require_POST
def update_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    action = request.POST.get('action')
    
    if action == 'up':
        if cart_item.quantity < cart_item.variant.stocks:
            cart_item.quantity += 1
        else:
            messages.warning(request, "Maximum stocks reached.")
    elif action == 'down':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
        else:
            cart_item.delete()
            return redirect('cart_detail')
    
    cart_item.save()
    return redirect('cart_detail')


@login_required

def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id = item_id, cart__user=request.user)
    cart_item.delete()
    messages.info(request, "Item removed from cart.")
    return redirect('cart_detail')

@login_required
def checkout_view(request):
    item_ids_str = request.GET.get('items', '')
    if not item_ids_str:
        return redirect('cart_detail') 

    try:
        item_ids = [int(id) for id in item_ids_str.split(',') if id.strip()]
    except ValueError:
        return redirect('cart_detail')

    cart_items = CartItem.objects.filter(
        id__in=item_ids, 
        cart__user=request.user
    ).select_related('variant__product')
    
    if not cart_items.exists():
        return redirect('cart_detail')

    total_price = sum(item.get_cost() for item in cart_items)


    item_methods = [item.variant.product.accepted_payments for item in cart_items]  
    
    can_use_gcash = all(m in ['GCASH', 'BOTH'] for m in item_methods)
    can_use_cop = all(m in ['COP', 'BOTH'] for m in item_methods)

    unique_locations = MeetupLocation.objects.filter(
        is_active=True
    ).values_list('name', flat=True).order_by('name')
    
    context = {
        'items': cart_items,
        'total_price': total_price,
        'user': request.user,
        'available_locations': unique_locations,
        'can_use_gcash': can_use_gcash,
        'can_use_cop': can_use_cop,
    }   
    return render(request, 'UTrade_app/cart/checkout.html', context)