// ================= GLOBAL SAFE INIT =================
let variantData = [];
const variantDataElement = document.getElementById('variant-data');
if (variantDataElement) {
    try {
        variantData = JSON.parse(variantDataElement.textContent);
    } catch (e) {
        console.error("Variant JSON parse error:", e);
    }
}

// ================= WISHLIST =================
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
                Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: 'Added to Wishlist', showConfirmButton: false, timer: 1500 });
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

                Swal.fire({ toast: true, position: 'top-end', icon: 'info', title: 'Removed from Wishlist', showConfirmButton: false, timer: 1500 });
            }
        }
    } catch {
        Swal.fire('Oops!', 'Something went wrong. Are you logged in?', 'error');
    }
}

// ================= IMAGE + VARIANT DISPLAY =================
function updateProductDisplay(variant) {
    if (!variant) return;

    const priceEl = document.getElementById('displayPrice');
    const detailsDiv = document.getElementById('variantDetails');
    const flawsEl = document.getElementById('variantFlaws');
    const conditionBadge = document.getElementById('variantConditionBadge');
    const nameDisplay = document.getElementById('variantNameDisplay');

    if (priceEl) priceEl.innerText = `₱${variant.price}`;
    if (detailsDiv) detailsDiv.classList.remove('d-none');
    if (nameDisplay) nameDisplay.innerText = variant.name;
    if (conditionBadge) conditionBadge.innerText = variant.condition;
    if (flawsEl) flawsEl.innerText = `Notes: ${variant.flaws}`;

    const img = document.getElementById('mainDisplayImage');
    if (img) img.src = variant.image_url;
}

function changeImage(url, element = null) {
    const mainImg = document.getElementById('mainDisplayImage');
    if (mainImg) {
        mainImg.style.opacity = '0';
        setTimeout(() => {
            mainImg.src = url;
            mainImg.style.opacity = '1';
        }, 200);
    }

    document.querySelectorAll('.thumbnail-wrapper').forEach(el => {
        el.classList.remove('border-success', 'border-2');
    });

    if (element) {
        element.classList.add('border-success', 'border-2');
    }

    const matchedVariant = variantData.find(v => v.image_url.includes(url));
    if (matchedVariant) {
        updateProductDisplay(matchedVariant);
    }
}

// ================= VARIANT CHANGE =================
function onVariantChange(variantId) {
    const selectedVariant = variantData.find(v => v.id == variantId);

    if (selectedVariant) {
        changeImage(selectedVariant.image_url);

        const priceDisplay = document.querySelector('.display-5');
        if (priceDisplay) {
            priceDisplay.innerText = `₱${selectedVariant.price}`;
        }
    }
}

// ================= VARIANT SELECTOR =================
function openVariantSelector(productId, productName, isPreOrder = false) {
    if (!variantData || variantData.length === 0) {
        addToCart(productId, null);
        return;
    }

    let variantHtml = `
        <div class="text-start mb-2 mt-3 px-1">
            <small class="text-muted text-uppercase fw-bold" style="font-size: 0.7rem;">Available Options</small>
        </div>
        <div class="list-group text-start">`;

    variantData.forEach(v => {
        const isOut = v.stock <= 0;

        variantHtml += `
            <label class="list-group-item list-group-item-action d-flex justify-content-between align-items-center rounded-3 mb-2 border ${isOut ? 'opacity-50 bg-light' : ''}">
                <div class="d-flex align-items-center">
                    <input class="form-check-input me-3 border-success" type="radio" name="swal-variant" value="${v.id}" ${isOut ? 'disabled' : ''}>
                    <div class="variant-img-wrapper rounded me-3 border" style="width:40px;height:40px;overflow:hidden;">
                        <img src="${v.image_url}" style="width:100%;height:100%;object-fit:cover;">
                    </div>
                    <div>
                        <div class="fw-bold">${v.name}</div>
                        <div class="text-success small">₱${v.price}</div>
                    </div>
                </div>
                ${isOut ? '<span class="badge bg-danger">Sold Out</span>' : `<span class="badge bg-success-subtle text-success">Stock: ${v.stock}</span>`}
            </label>`;
    });

    variantHtml += `</div>`;

    Swal.fire({
        title: isPreOrder ? `Pre-order ${productName}` : `Add ${productName} to Cart`,
        html: variantHtml,
        showCancelButton: true,
        confirmButtonText: isPreOrder ? 'Confirm Pre-order' : 'Add to Cart',
        confirmButtonColor: isPreOrder ? '#0d6efd' : '#198754',

        didRender: () => {
            const radios = Swal.getHtmlContainer().querySelectorAll('input[name="swal-variant"]');

            radios.forEach(radio => {
                radio.addEventListener('change', e => {
                    const v = variantData.find(x => x.id == e.target.value);
                    if (v) changeImage(v.image_url);
                });
            });
        },

        preConfirm: () => {
            const selected = document.querySelector('input[name="swal-variant"]:checked');
            if (!selected) {
                Swal.showValidationMessage('Please select a variation');
                return false;
            }
            return selected.value;
        }
    }).then(result => {
        if (result.isConfirmed) {
            isPreOrder ? performPreOrderRequest(result.value) : performAddToCart(result.value);
        }
    });
}

// ================= PREORDER =================
function performPreOrderRequest(variantId) {
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    fetch(`/preorder/request/${variantId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ status: 'Pending' })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            Swal.fire({ icon: 'success', title: 'Request Sent!', text: 'Pending seller approval.' });
        } else {
            Swal.fire({ icon: 'error', title: 'Error', text: data.message });
        }
    })
    .catch(() => Swal.fire('Connection Error', 'Try again later', 'error'));
}

// ================= ADD TO CART (VARIANT) =================
function performAddToCart(variantId) {
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    fetch(`/cart/add/${variantId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ quantity: 1 })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const badge = document.getElementById('cart-count');
            if (badge) {
                badge.innerText = data.cart_count;
                badge.style.display = 'block';
            }

            Swal.fire({ icon: 'success', title: 'Added to Cart!', timer: 1500, showConfirmButton: false });
        } else {
            Swal.fire({ icon: 'error', title: 'Error', text: data.message });
        }
    })
    .catch(() => Swal.fire('Error', 'Login required', 'error'));
}

// ================= SIMPLE ADD TO CART =================
function addToCart(productId, buttonElement) {
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    fetch(`/cart/add/${productId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const badge = document.getElementById('cart-count');
            if (badge) {
                badge.innerText = data.cart_count;
                badge.style.display = 'inline-block';
            }

            Swal.fire({ toast: true, position: 'top-end', icon: 'success', title: 'Added to Cart', timer: 1500, showConfirmButton: false });
        } else {
            Swal.fire({ icon: 'error', title: 'Error', text: data.message });
        }
    })
    .catch(() => Swal.fire('Login Required', '', 'warning'));
}

// ================= HELPERS =================
function addToCartWithVariant(productId) {
    const name = document.querySelector('h1')?.innerText || "Product";
    openVariantSelector(productId, name);
}

function showLoginPrompt() {
    const loginUrl = document.getElementById('login-url').value;

    Swal.fire({
        title: 'Login Required',
        text: 'You need to log in first.',
        icon: 'info',
        showCancelButton: true,
        confirmButtonText: 'Login'
    }).then(r => {
        if (r.isConfirmed) window.location.href = loginUrl;
    });
}

function showVerificationModal() {
    const status = document.getElementById('user-verification-status').value;

    if (status === 'unverified' || status === 'Pending') {
        const modal = new bootstrap.Modal(document.getElementById('verificationModal'));
        modal.show();
    }
}