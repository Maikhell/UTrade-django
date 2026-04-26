// Updates the main image display with a fade effect and manages thumbnail border styling
function changeImage(url, element) {
    const mainDisplay = document.getElementById('mainDisplayImage');
    if (!mainDisplay) return;

    mainDisplay.style.opacity = '0';
    setTimeout(() => {
        mainDisplay.src = url;
        mainDisplay.style.opacity = '1';
    }, 200);

    if (element) {
        document.querySelectorAll('.thumbnail-wrapper').forEach(el => {
            el.classList.remove('border-success', 'border-2');
        });
        element.classList.add('border-success', 'border-2');
    }
}

// Finds the selected variant data to update the main image and price display
function onVariantChange(variantId) {
    const variantData = JSON.parse(document.getElementById('variant-data').textContent);
    const selectedVariant = variantData.find(v => v.id == variantId);

    if (selectedVariant) {
        changeImage(selectedVariant.image_url);

        const priceDisplay = document.querySelector('.display-5');
        if (priceDisplay) {
            priceDisplay.innerText = `₱${selectedVariant.price}`;
        }
    }
}

// Generates an HTML list of variants and displays them in a selection modal
function openVariantSelector(productId, productName) {
    const variantDataElement = document.getElementById('variant-data');
    if (!variantDataElement) return;

    const variants = JSON.parse(variantDataElement.textContent);

    let variantHtml = `
        <div class="text-start mb-2 mt-3 px-1">
            <small class="text-muted text-uppercase fw-bold" style="font-size: 0.7rem;">Available Options</small>
        </div>
        <div class="list-group text-start" id="variant-options-list">`;

    variants.forEach(v => {
        const isOutOfStock = v.stock <= 0;
        variantHtml += `
            <label class="list-group-item list-group-item-action d-flex justify-content-between align-items-center rounded-3 mb-2 border ${isOutOfStock ? 'opacity-50 bg-light' : ''}" 
                   style="cursor: ${isOutOfStock ? 'not-allowed' : 'pointer'}; padding: 12px 15px;">
                <div class="d-flex align-items-center flex-grow-1">
                    <input class="form-check-input me-3 border-success" type="radio" name="swal-variant" value="${v.id}" ${isOutOfStock ? 'disabled' : ''}>
                    <div class="variant-img-wrapper rounded me-3 border" style="width: 40px; height: 40px; overflow: hidden;">
                        <img src="${v.image_url}" style="width: 100%; height: 100%; object-fit: cover;">
                    </div>
                    <div class="flex-grow-1">
                        <div class="fw-bold text-dark">${v.name}</div>
                        <div class="text-success small fw-bold">₱${v.price}</div>
                    </div>
                </div>
                ${isOutOfStock ? '<span class="badge bg-danger rounded-pill">Sold Out</span>' : `<span class="badge bg-success-subtle text-success">Stock: ${v.stock}</span>`}
            </label>`;
    });
    variantHtml += '</div>';

    Swal.fire({
        title: `Add ${productName} to Cart`,
        html: variantHtml,
        showCancelButton: true,
        confirmButtonText: 'Add to Cart',
        confirmButtonColor: '#198754', // Bootstrap Success Color
        preConfirm: () => {
            const selectedVariant = document.querySelector('input[name="swal-variant"]:checked');
            if (!selectedVariant) {
                Swal.showValidationMessage('Please select a variation first');
                return false;
            }
            return selectedVariant.value;
        }
    }).then((result) => {
        if (result.isConfirmed) {
            // Send to your Django View
            performAddToCart(result.value);
        }
    });
}
function performAddToCart(variantId) {
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    // 1. Log to console to verify the URL being called
    console.log("Calling URL:", `/cart/add/${variantId}/`);

    fetch(`/cart/add/${variantId}/`, {  
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest' // Helps Django identify AJAX
        },
        body: JSON.stringify({ 'quantity': 1 })
    })
    .then(response => {
        // 2. Check if the server actually returned a success status
        if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const cartCountBadge = document.getElementById('cart-count');
            if (cartCountBadge) {
                cartCountBadge.innerText = data.cart_count;
                cartCountBadge.style.display = 'block';
            }

            Swal.fire({
                icon: 'success',
                title: 'Added to Cart!',
                text: 'Your item is waiting in the shopping cart.',
                showConfirmButton: false,
                timer: 1500,
                iconColor: '#198754'
            });
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Could not add to cart',
                text: data.message || 'Check stock availability.',
                confirmButtonColor: '#198754'
            });
        }
    })
    .catch(error => {
        console.error('Full Error Object:', error);
        Swal.fire({
            icon: 'error',
            title: 'Connection Error',
            text: 'Ensure you are logged in and the server is reachable.',
            confirmButtonColor: '#d33'
        });
    });
}

function addToCartWithVariant(productId) {
    const productName = document.querySelector('h1')?.innerText || "Product";
    openVariantSelector(productId, productName);
}

const variantData = JSON.parse(document.getElementById('variant-data').textContent);

// Updates price, details, flaws, and condition badges for a specific variant
function updateProductDisplay(variant) {
    const priceEl = document.getElementById('displayPrice');
    const detailsDiv = document.getElementById('variantDetails');
    const flawsEl = document.getElementById('variantFlaws');
    const conditionBadge = document.getElementById('variantConditionBadge');
    const nameDisplay = document.getElementById('variantNameDisplay');

    if (variant) {
        priceEl.innerText = `₱${variant.price}`;

        detailsDiv.classList.remove('d-none');
        nameDisplay.innerText = variant.name;
        conditionBadge.innerText = variant.condition;
        flawsEl.innerText = `Notes: ${variant.flaws}`;

        document.getElementById('mainDisplayImage').src = variant.image_url;
    }
}

// Switches the main image and updates the full product display if a matching variant is found
function changeImage(url, element) {
    document.getElementById('mainDisplayImage').src = url;

    document.querySelectorAll('.thumbnail-wrapper').forEach(el => el.classList.remove('border-success', 'border-2'));
    element.classList.add('border-success', 'border-2');


    const matchedVariant = variantData.find(v => v.image_url.includes(url));
    if (matchedVariant) {
        updateProductDisplay(matchedVariant);
    }
}