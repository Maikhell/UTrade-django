from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from ..models import Product, Cart, CartItem

@login_required
def cart_detail(request):
    cart = request.user.cart
    return render(request, 'UTrade_app/cart/cart_detail.html',{
        'cart': cart,
        'cart_items': cart.items.all(),
        'toral_price': cart.total_price
    })
@login_required
@require_POST
def add_to_cart(request, product_id):
    if request.method == 'POST':
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'message': 'Please login first'}, status=401)

        product = get_object_or_404(Product, id=product_id)
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        
        if not created:
            cart_item.quantity += 1
            cart_item.save()

        return JsonResponse({
            'status': 'success',
            'cart_count': cart.items.count(), 
        })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
@login_required
@require_POST
def update_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    action = request.POST.get('action')
    
    if action == 'up':
        if cart_item.quantity < cart_item.product.stocks:
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


    