// Wishlist Function
async function toggleWishlist(productId, buttonElement, isWishlistPage = false) {
    const icon = buttonElement.querySelector('i');
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    try {
        const response = await fetch(`/wishlist/toggle/${productId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken,
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        const data = await response.json();
        if (data.status === 'success') {
            if (data.action === 'added') {
                icon.classList.replace('bi-heart', 'bi-heart-fill');
                Swal.fire({
                    toast: true,
                    position: 'top-end',
                    icon: 'success',
                    title: 'Added to Wishlist',
                    showConfirmButton: false,
                    timer: 1500
                });
            } else {
                icon.classList.replace('bi-heart-fill', 'bi-heart');
                
                // Handles the smooth removal of the product card specifically when on the Wishlist page
                if (isWishlistPage) {
                    const card = document.getElementById(`wishlist-item-${productId}`);
                    if (card) {
                        card.style.transition = '0.3s';
                        card.style.opacity = '0';
                        card.style.transform = 'scale(0.9)';
                        setTimeout(() => card.remove(), 300);
                    }
                }
                Swal.fire({
                    toast: true,
                    position: 'top-end',
                    icon: 'info',
                    title: 'Removed from Wishlist',
                    showConfirmButton: false,
                    timer: 1500
                });
            }
        }
    } catch (error) {
        Swal.fire('Oops!', 'Something went wrong. Are you logged in?', 'error');
    }
} 

function addToCart(productId, buttonElement) {
    const icon = buttonElement.querySelector('i');
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    
    fetch(`/cart/add/${productId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Updates the button UI to show a "checked" state after a successful server response
            if (icon) {
                icon.classList.replace('bi-cart-plus', 'bi-cart-check-fill');
                buttonElement.classList.add('btn-success'); 
            }

            // Real-Time Badge Update including a scale animation for visual feedback
            const badge = document.getElementById('cart-count');
            if (badge) {
                badge.innerText = data.cart_count;
                badge.style.display = 'inline-block';
                
                badge.animate([
                    { transform: 'scale(1)' },
                    { transform: 'scale(1.5)' },
                    { transform: 'scale(1)' }
                ], { duration: 300 });
            }

            Swal.fire({
                toast: true,
                position: 'top-end', 
                icon: 'success',
                title: 'Added to Cart',
                showConfirmButton: false,
                timer: 1500,
                timerProgressBar: true
            });
        }
    })
    .catch(error => console.error('Error:', error));
}