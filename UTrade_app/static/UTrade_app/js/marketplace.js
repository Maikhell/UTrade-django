// Wishlist Function
async function toggleWishlist(productId, buttonElement, isWishlistPage = false) {
    if (!buttonElement || typeof buttonElement.querySelector !== 'function') return;

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
    const isElement = buttonElement instanceof HTMLElement;
    const icon = isElement ? buttonElement.querySelector('i') : null;
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
        // CHANGED: Check for data.success to match your Django View
        if (data.success === true) {
            
            if (isElement && icon) {
                icon.classList.replace('bi-cart-plus', 'bi-cart-check-fill');
                buttonElement.classList.add('btn-success');
            }

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
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Wait!',
                text: data.message || 'Could not add item to cart.',
                confirmButtonColor: '#198754'
            });
        }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({
            icon: 'warning',
            title: 'Please Login',
            text: 'You need an account to add items to your cart.',
            confirmButtonColor: '#198754'
        });
    });
}
function changeImage(imageUrl, element) {
    const mainImg = document.getElementById('mainDisplayImage');
    if (mainImg) {
        mainImg.src = imageUrl;
    }

    document.querySelectorAll('.thumbnail-wrapper').forEach(wrapper => {
        wrapper.classList.remove('border-success', 'border-2');
    });
    if (element) {
        element.classList.add('border-success', 'border-2');
    }
}

function openVariantSelector(productId, productName, isPreorder = false) {
    const variantDataElement = document.getElementById('variant-data');
    if (!variantDataElement) {
        console.error("Variant data not found!");
        return;
    }

    const variants = JSON.parse(variantDataElement.textContent);

    if (variants.length === 0) {
        addToCart(productId, null);
        return;
    }

    let variantHtml = `
        <div class="text-start mb-2 mt-3 px-1">
            <small class="text-muted text-uppercase fw-bold" style="font-size: 0.7rem;">Available Options for ${productName}</small>
        </div>
        <div class="list-group text-start">`;

    variants.forEach(v => {
        const isOutOfStock = v.stock <= 0;
        const disabledAttr = isOutOfStock ? 'disabled' : '';
        const opacityClass = isOutOfStock ? 'opacity-50 bg-light' : '';
        const badge = isOutOfStock ? '<span class="badge bg-danger rounded-pill">Sold Out</span>' : `<span class="badge bg-success-subtle text-success rounded-pill">Stock: ${v.stock}</span>`;

        variantHtml += `
            <label class="list-group-item list-group-item-action d-flex justify-content-between align-items-center rounded-3 mb-2 border ${opacityClass}" 
                    style="cursor: ${isOutOfStock ? 'not-allowed' : 'pointer'}; padding: 12px 15px;">
                <div class="d-flex align-items-center">
                    <input class="form-check-input me-3 border-success" type="radio" name="swal-variant" value="${v.id}" ${disabledAttr}>
                    <div>
                        <div class="fw-bold text-dark">${v.name}</div>
                        <div class="text-success small fw-bold">₱${v.price}</div>
                    </div>
                </div>
                <div>
                    ${badge}
                </div>
            </label>
        `;
    });
    variantHtml += '</div>';

    Swal.fire({
        title: 'Choose Variation',
        html: variantHtml,
        showCancelButton: true,
        // Fixed: Combined logic into single properties to prevent overwriting
        confirmButtonText: isPreorder ? '<i class="bi bi-calendar-check me-2"></i> Pre-order Now' : '<i class="bi bi-cart-plus me-2"></i> Add to Cart',
        confirmButtonColor: isPreorder ? '#0d6efd' : '#198754',
        cancelButtonText: 'Cancel',
        cancelButtonColor: '#6c757d',
        customClass: {
            popup: 'rounded-4 shadow',
            confirmButton: 'rounded-pill px-4 py-2 fw-bold',
            cancelButton: 'rounded-pill px-4 py-2'
        },
        didRender: () => {
            const swalContainer = Swal.getHtmlContainer();
            const radios = swalContainer.querySelectorAll('input[name="swal-variant"]');

            radios.forEach(radio => {
                radio.addEventListener('change', (e) => {
                    const selectedVariantId = e.target.value;
                    const variant = variants.find(v => v.id == selectedVariantId);

                    if (variant && variant.image_url) {
                        const mainImg = document.getElementById('mainDisplayImage');
                        if (mainImg) {
                            mainImg.src = variant.image_url;
                        }
                    }
                });
            });
        },
        preConfirm: () => {
            const selected = document.querySelector('input[name="swal-variant"]:checked');
            if (!selected) {
                Swal.showValidationMessage('Please select a variation to continue');
                return false;
            }
            return selected.value;
        }
    }).then((result) => {
        if (result.isConfirmed) {
            addToCart(result.value, null);
        }
    });
}

function addToCartWithVariant(productId) {
    const productName = document.querySelector('h1')?.innerText || "Product";
    openVariantSelector(productId, productName);
}

function showLoginPrompt() {
    const loginUrl = document.getElementById('login-url').value;

    Swal.fire({
        title: 'Join the Community!',
        text: 'You need to be logged in to view full product details.',
        icon: 'info',
        showCancelButton: true,
        confirmButtonText: 'Login Now',
        confirmButtonColor: '#198754',
    }).then((result) => {
        if (result.isConfirmed) {
            window.location.href = loginUrl;
        }
    });
}

function showVerificationModal() {
    const userStatus = document.getElementById('user-verification-status').value;

    if (userStatus === 'unverified' || userStatus === 'Pending') {
        const modalEl = document.getElementById('verificationModal');
        if (modalEl) {
            const vModal = new bootstrap.Modal(modalEl);
            vModal.show();
        }
    } else {
        console.log("User status is:", userStatus, "- skipping modal.");
    }
}