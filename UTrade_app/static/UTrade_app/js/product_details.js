function changeImage(imageUrl, element) {
    document.getElementById('mainDisplayImage').src = imageUrl;
    document.querySelectorAll('.thumbnail-wrapper').forEach(wrapper => {
        wrapper.classList.remove('border-success', 'border-2');
    });
    element.classList.add('border-success', 'border-2');
}

document.addEventListener('DOMContentLoaded', function() {
    const variantRadios = document.querySelectorAll('input[name="product_variant"]');
    const stockDisplay = document.getElementById('variant-stock-display');

    variantRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            const stock = this.getAttribute('data-stock');
            stockDisplay.innerText = stock;
            
            if (parseInt(stock) < 5) {
                stockDisplay.classList.add('text-danger');
                stockDisplay.classList.remove('text-dark');
            } else {
                stockDisplay.classList.add('text-dark');
                stockDisplay.classList.remove('text-danger');
            }
        });
    });
});

function addToCartWithVariant(productId) {
    const variantOptions = document.querySelectorAll('input[name="product_variant"]');
    const selectedVariant = document.querySelector('input[name="product_variant"]:checked');
    
    if (variantOptions.length > 0 && !selectedVariant) {
        Swal.fire({
            icon: 'warning',
            title: 'Please select an option',
            text: 'Choose a variation (like Size or Color) before adding to cart.',
            confirmButtonColor: '#198754'
        });
        return;
    }
    const finalId = selectedVariant ? selectedVariant.value : productId;
    const isVariant = selectedVariant ? true : false;
    addToCart(finalId, isVariant); 
}