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

function openVariantSelector(productId, productName) {
    // Retrieve variant data from the JSON script tag added to the HTML
    const variantDataElement = document.getElementById('variant-data');
    if (!variantDataElement) {
        console.error("Variant data not found!");
        return;
    }

    const variants = JSON.parse(variantDataElement.textContent);

    // If there are no variants at all, add the base product directly
    if (variants.length === 0) {
        addToCart(productId, false);
        return;
    }

    // Generate the HTML for the variation list inside the popup
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

    // Show the SweetAlert Popup
    Swal.fire({
        title: 'Choose Variation',
        html: variantHtml,
        showCancelButton: true,
        confirmButtonText: 'Add to Cart',
        confirmButtonColor: '#198754', 
        cancelButtonText: 'Cancel',
        cancelButtonColor: '#6c757d',
        customClass: {
            popup: 'rounded-4 shadow',
            confirmButton: 'rounded-pill px-4 py-2 fw-bold',
            cancelButton: 'rounded-pill px-4 py-2'
        },
        didRender: () => {
            // Listen for changes on the radio buttons inside the SweetAlert
            const swalContainer = Swal.getHtmlContainer();
            const radios = swalContainer.querySelectorAll('input[name="swal-variant"]');
            
            radios.forEach(radio => {
                radio.addEventListener('change', (e) => {
                    const selectedVariantId = e.target.value;
                    const variant = variants.find(v => v.id == selectedVariantId);
                    
                    // If the variant has a specific image, update the main display
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
            addToCart(result.value, true);
        }
    });
}

function addToCartWithVariant(productId) {
    const productName = document.querySelector('h1')?.innerText || "Product";
    openVariantSelector(productId, productName);
}