from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
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
    cart = request.user.cart
    product = get_object_or_404(Product, id = product_id)
    
    if product.stocks < 1:
        messages.error(request, f"Sorry, {product.name} is currently out of stocks." )
        return redirect ('product_detail', pk=product_id)
    cart_item, created = CartItem.objects.get_or_create(cart = cart, product=product)
    
    if not created:
        cart_item.quantity += 1
        cart_item.save()
        
    messages.success(request, f"{product.name} added to your cart!")
    return redirect('card_detail')

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
    return redirect('card_detail')


@login_required

def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id = item_id, cart__user=request.user)
    cart_item.delete()
    messages.info(request, "Item removed from cart.")
    return redirect('cart_detail')


    