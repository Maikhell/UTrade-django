function changeImage(url, element) {
    const mainDisplay = document.getElementById('mainDisplayImage');
    if (!mainDisplay) return;

    // Change the image source with a fade effect
    mainDisplay.style.opacity = '0';
    setTimeout(() => {
        mainDisplay.src = url;
        mainDisplay.style.opacity = '1';
    }, 200);

    // Update thumbnail border styling
    if (element) {
        document.querySelectorAll('.thumbnail-wrapper').forEach(el => {
            el.classList.remove('border-success', 'border-2');
        });
        element.classList.add('border-success', 'border-2');
    }
}
function onVariantChange(variantId) {
    const variantData = JSON.parse(document.getElementById('variant-data').textContent);
    const selectedVariant = variantData.find(v => v.id == variantId);

    if (selectedVariant) {
        // 1. Swap the Main Image to the Variant's Image
        changeImage(selectedVariant.image_url);

        // 2. Update Price Display (optional)
        const priceDisplay = document.querySelector('.display-5');
        if (priceDisplay) {
            priceDisplay.innerText = `₱${selectedVariant.price}`;
        }
    }
}
function openVariantSelector(productId, productName) {
    // 1. Retrieve the (now updated) variant data
    const variantDataElement = document.getElementById('variant-data');
    if (!variantDataElement) return; // or handle base product directly

    const variants = JSON.parse(variantDataElement.textContent);

    // ... (rest of your logic for base product if variants.length === 0) ...

    // 2. Generate the Updated HTML
    let variantHtml = `
        <div class="text-start mb-2 mt-3 px-1">
            <small class="text-muted text-uppercase fw-bold" style="font-size: 0.7rem;">Available Options for ${productName}</small>
        </div>
        <div class="list-group text-start">`;

    variants.forEach(v => {
        const isOutOfStock = v.stock <= 0;
        const disabledAttr = isOutOfStock ? 'disabled' : '';
        const opacityClass = isOutOfStock ? 'opacity-50 bg-light' : '';

        // Define the stock badge
        const badge = isOutOfStock
            ? '<span class="badge bg-danger rounded-pill">Sold Out</span>'
            : `<span class="badge bg-success-subtle text-success rounded-pill">Stock: ${v.stock}</span>`;

        variantHtml += `
            <label class="list-group-item list-group-item-action d-flex justify-content-between align-items-center rounded-3 mb-2 border ${opacityClass}" 
                   style="cursor: ${isOutOfStock ? 'not-allowed' : 'pointer'}; padding: 12px 15px;">
                <div class="d-flex align-items-center flex-grow-1">
                    <input class="form-check-input me-3 border-success" type="radio" name="swal-variant" value="${v.id}" ${disabledAttr}>
                    
                    <div class="variant-img-wrapper rounded me-3 overflow-hidden border" style="width: 40px; height: 40px;">
                        <img src="${v.image_url}" alt="${v.name}" style="width: 100%; height: 100%; object-fit: cover;">
                    </div>
                    
                    <div class="flex-grow-1">
                        <div class="fw-bold text-dark">${v.name}</div>
                        <div class="text-success small fw-bold">₱${v.price}</div>
                    </div>
                </div>
                <div class="ms-3">
                    ${badge}
                </div>
            </label>
        `;
    });
    variantHtml += '</div>';

    // 3. Keep your existing logic for main image update on selection
    Swal.fire({
        title: 'Choose Variation',
        html: variantHtml,
        // ... (rest of your existing logic for image updates, didRender, etc.) ...
    });
}

function addToCartWithVariant(productId) {
    const productName = document.querySelector('h1')?.innerText || "Product";
    openVariantSelector(productId, productName);
}
// Load the data from the script tag
const variantData = JSON.parse(document.getElementById('variant-data').textContent);

function updateProductDisplay(variant) {
    const priceEl = document.getElementById('displayPrice');
    const detailsDiv = document.getElementById('variantDetails');
    const flawsEl = document.getElementById('variantFlaws');
    const conditionBadge = document.getElementById('variantConditionBadge');
    const nameDisplay = document.getElementById('variantNameDisplay');

    if (variant) {
        // Update Price
        priceEl.innerText = `₱${variant.price}`;

        // Show and Update Flaws/Condition
        detailsDiv.classList.remove('d-none');
        nameDisplay.innerText = variant.name;
        conditionBadge.innerText = variant.condition;
        flawsEl.innerText = `Notes: ${variant.flaws}`;

        // Update Main Image if variant has one
        document.getElementById('mainDisplayImage').src = variant.image_url;
    }
}

// Update the existing changeImage function to search for the variant
function changeImage(url, element) {
    // 1. Update the Main Image src
    document.getElementById('mainDisplayImage').src = url;

    // 2. Highlighting the thumbnail
    document.querySelectorAll('.thumbnail-wrapper').forEach(el => el.classList.remove('border-success', 'border-2'));
    element.classList.add('border-success', 'border-2');

    // 3. Find if this image belongs to a specific variant
    const matchedVariant = variantData.find(v => v.image_url.includes(url));
    if (matchedVariant) {
        updateProductDisplay(matchedVariant);
    }
}