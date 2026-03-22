let itemCount = 0;
let currentAttributes = { sizes: [], varieties: [], colors: [] };
let selectedFiles = [];
let allStagedProducts = [];
let productVariants = [];

window.sizePresets = {
    Clothes: ['S', 'M', 'L', 'XL', 'XXL'],
    Clothing: ['S', 'M', 'L', 'XL', 'XXL'],
    Shoes: ['38', '39', '40', '41', '42', '43', '44'],
    Footwear: ['38', '39', '40', '41', '42', '43', '44']
};
function previewMultipleImages(event) {
    const container = document.getElementById('image_preview_container');
    container.innerHTML = '';
    selectedFiles = Array.from(event.target.files);

    selectedFiles.forEach((file, index) => {
        const reader = new FileReader();
        reader.onload = function (e) {
            const wrapper = document.createElement('div');
            wrapper.className = 'preview-wrapper animate__animated animate__fadeIn';
            const isMain = index === 0;
            const badge = isMain ? '<span class="main-badge">COVER</span>' : '';
            wrapper.innerHTML = `
                ${badge}
                <img src="${e.target.result}" 
                     class="preview-box ${isMain ? 'is-main-image' : ''}">
            `;
            container.appendChild(wrapper);
        }
        reader.readAsDataURL(file);
    });
}

function addTag(type) {
    const input = document.getElementById(`${type}_input`);
    const tagContainer = document.getElementById(`${type}_tags`);
    const mainDisplay = document.getElementById('attribute_pills');
    const val = input.value.trim();
    if (!val) return;
    if (!currentAttributes[`${type}s`].includes(val)) {
        currentAttributes[`${type}s`].push(val);
        const pillHtml = `
                <span class="badge rounded-pill bg-light text-dark border p-2 me-1 mb-1">
                    ${val} <i class="bi bi-x-circle-fill ms-1 text-danger cursor-pointer" onclick="removeTag('${type}', '${val}', this)"></i>
                </span>`;
        mainDisplay.insertAdjacentHTML('beforeend', pillHtml);
        tagContainer.insertAdjacentHTML('beforeend', pillHtml);
    }
    input.value = '';
}

// Toggle other Category
function toggleOtherCategory(select) {
    const otherDiv = document.getElementById('other_category_div');
    if (select.value === 'other') {
        otherDiv.classList.remove('d-none');
    } else {
        otherDiv.classList.add('d-none');
    }

}
function addToStaging() {
    // 1. Get Elements
    const nameEl = document.getElementById('name');
    const priceEl = document.getElementById('price');
    const stocksEl = document.getElementById('stocks');
    const descEl = document.getElementById('description');
    const categoryEl = document.getElementById('category');

    // 2. Determine Mode (Check if attributes section is visible)
    const isVariantMode = !document.getElementById('attributes_section').classList.contains('d-none');

    // 3. Reset Validation Errors
    [nameEl, priceEl, stocksEl].forEach(el => el.classList.remove('is-invalid'));

    let hasError = false;

    // 4. Validate Name (Required for everyone)
    if (!nameEl.value.trim()) {
        nameEl.classList.add('is-invalid');
        hasError = true;
    }

    // 5. Context-Aware Validation
    let finalPrice, finalStocks;

    if (isVariantMode) {
        // VALIDATION FOR CLOTHES/SHOES/ETC
        if (productVariants.length === 0) {
            Swal.fire('Variations Required', 'Please add at least one size or variety using the "Add" button.', 'warning');
            return; // Stop execution
        }
        // In variant mode, we pull price from the first variant and total stock from the sum
        finalPrice = productVariants[0].price;
        finalStocks = productVariants.reduce((sum, v) => sum + v.stock, 0);
    } else {
        // VALIDATION FOR SIMPLE ITEMS
        if (!priceEl.value.trim()) { priceEl.classList.add('is-invalid'); hasError = true; }
        if (!stocksEl.value.trim()) { stocksEl.classList.add('is-invalid'); hasError = true; }
        finalPrice = priceEl.value;
        finalStocks = stocksEl.value;
    }

    // 6. Image Check
    if (selectedFiles.length === 0) {
        Swal.fire('Photos Required', 'Please select at least one photo for your product.', 'warning');
        return;
    }

    // 7. Stop if basic fields are missing
    if (hasError) {
        return Swal.fire({
            title: 'Required Fields',
            text: 'Please fill in the red-highlighted fields.',
            icon: 'error',
            confirmButtonColor: '#dc3545'
        });
    }

    // 8. Handle Category Logic
    let categoryId = categoryEl.value;
    let categoryName = categoryEl.options[categoryEl.selectedIndex].text;

    if (categoryId === 'other') {
        const customValue = document.getElementById('custom_category').value.trim();
        categoryId = `NEW:${customValue}`;
        categoryName = customValue;
    }

    // 9. Gather other data
    const condition = document.getElementById('condition').value;
    const meetup = document.getElementById('meetup').value;
    const productId = Date.now();
    const paymentEl = document.querySelector('input[name="payment"]:checked');
    const payment = paymentEl ? paymentEl.value : 'Not Specified';

    // 10. Package Data
    const productData = {
        id: productId,
        name: nameEl.value,
        price: finalPrice,
        stocks: finalStocks,
        description: descEl.value,
        category: categoryId,
        condition: condition,
        meetup: meetup,
        payment: payment,
        files: [...selectedFiles],
        variants: [...productVariants]
    };

    allStagedProducts.push(productData);

    // 11. Update UI
    itemCount = allStagedProducts.length;
    document.getElementById('item_count').innerText = itemCount;

    const stagingArea = document.getElementById('staging_area');
    if (stagingArea.querySelector('.empty-msg')) stagingArea.innerHTML = '';

    const firstImagePreview = document.querySelector('#image_preview_container img');
    const firstImageSrc = firstImagePreview ? firstImagePreview.src : null;

    const imageHtml = firstImageSrc
        ? `<img src="${firstImageSrc}" class="rounded shadow-sm me-3" style="width: 70px; height: 70px; object-fit: cover; border: 1px solid #dee2e6;">`
        : `<div class="bg-light rounded me-3 d-flex align-items-center justify-content-center" style="width: 70px; height: 70px; border: 1px solid #dee2e6;"><i class="bi bi-image text-muted"></i></div>`;

    const itemCard = `
        <div class="card staged-item mb-3 p-3 bg-white border-0 shadow-sm animate__animated animate__fadeInRight" data-id="${productId}">
            <div class="d-flex align-items-start mb-2">
                ${imageHtml}
                <div class="flex-grow-1">
                    <div class="d-flex justify-content-between">
                        <h6 class="mb-0 fw-bold text-dark">${productData.name}</h6>
                        <button class="btn btn-sm text-danger p-0" onclick="removeItem(this, ${productId})">
                            <i class="bi bi-trash-fill"></i>
                        </button>
                    </div>
                    <div class="mt-1">
                        <span class="badge bg-success-subtle text-success small">₱${productData.price}</span>
                        <span class="text-muted small ms-1">Stock: ${productData.stocks}</span>
                    </div>
                </div>
            </div>
            <div class="small text-muted mb-2 text-truncate-2" style="font-size: 0.85rem;">${productData.description}</div>
            <div class="d-flex flex-wrap gap-1 mb-2">
                <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-tag me-1"></i>${categoryName}</span>
                <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-geo-alt me-1"></i>${meetup}</span>
                <span class="badge ${payment === 'GCash' ? 'bg-primary' : 'bg-success'} text-white fw-normal">
                    <i class="bi bi-wallet2 me-1"></i>${payment}
                </span>
            </div>
        </div>`;

    stagingArea.insertAdjacentHTML('afterbegin', itemCard);

    // 12. Final Reset
    document.getElementById('product_form').reset();
    productVariants = [];
    document.getElementById('variant_list').innerHTML = '';
    document.getElementById('attribute_pills').innerHTML = '';
    document.getElementById('image_preview_container').innerHTML = `
        <div class="text-center py-5 text-muted small w-100">
            <i class="bi bi-check-circle-fill text-success d-block mb-2" style="font-size: 2rem;"></i>
            Item added. Ready for next.
        </div>`;

    // Reset category-specific UI
    handleCategoryChange(categoryEl);
}
async function submitToAdmin() {
    if (allStagedProducts.length === 0) {
        return Swal.fire({
            title: 'Empty List',
            text: 'Your staging list is empty! Add items first.',
            icon: 'error',
            confirmButtonColor: '#198754'
        });
    }
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    if (!csrftoken) {
        return Swal.fire('Error', 'CSRF Token missing. Check your HTML template!', 'error');
    }
    const confirmation = await Swal.fire({
        title: 'Submit for Authorization?',
        text: `Are you sure you want to send ${allStagedProducts.length} item(s) for review?`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#198754',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Yes, submit it!',
        cancelButtonText: 'Wait, let me check'
    });

    if (!confirmation.isConfirmed) return;
    Swal.fire({
        title: 'Sending to Admin...',
        text: 'Please wait while we process your request.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    const formData = new FormData();

    allStagedProducts.forEach((product, index) => {
        formData.append(`prod_${index}_name`, product.name);
        formData.append(`prod_${index}_price`, product.price);
        formData.append(`prod_${index}_stocks`, product.stocks);
        formData.append(`prod_${index}_desc`, product.description);
        formData.append(`prod_${index}_category`, product.category);
        formData.append(`prod_${index}_condition`, product.condition);
        formData.append(`prod_${index}_meetup`, product.meetup);
        formData.append(`prod_${index}_payment`, product.payment);
        formData.append(`prod_${index}_variants`, JSON.stringify(product.variants));
        product.files.forEach((file, fileIndex) => {
            formData.append(`prod_${index}_image_${fileIndex}`, file);
        });
        formData.append(`prod_${index}_image_count`, product.files.length);
    });

    formData.append('total_products', allStagedProducts.length);
    try {
        const response = await fetch(window.location.href, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
            body: formData
        });
        const result = await response.json();
        if (result.status === 'success') {
            await Swal.fire({
                icon: 'success',
                title: 'Success!',
                text: 'Your items have been sent for review.',
                confirmButtonColor: '#198754'
            });
            window.location.reload();
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Submission Failed',
                text: result.message || "Failed to save items."
            });
        }
    } catch (error) {
        console.error("Submission Error:", error);
        Swal.fire({
            icon: 'error',
            title: 'Connection Error',
            text: 'Something went wrong while connecting to the server.'
        });
    }
}
function removeItem(btn, productId) {
    btn.closest('.staged-item').remove();
    allStagedProducts = allStagedProducts.filter(item => item.id !== productId);
    itemCount = allStagedProducts.length;
    document.getElementById('item_count').innerText = itemCount;
    if (itemCount === 0) {
        document.getElementById('staging_area').innerHTML = '<div class="text-center py-5 text-muted small empty-msg">List is empty.</div>';
    }
}
function removeTag(type, value, element) {
    currentAttributes[`${type}s`] = currentAttributes[`${type}s`].filter(val => val !== value);
    element.parentElement.remove();
    const mainPills = document.getElementById('attribute_pills').querySelectorAll('.badge');
    mainPills.forEach(pill => {
        if (pill.innerText.trim().includes(value)) {
            pill.remove();
        }
    });
}


//CATEGORY VISIBILITY LOGIC
function handleCategoryChange(selectElement) {
    const selectedText = selectElement.options[selectElement.selectedIndex].text;
    const attrSection = document.getElementById('attributes_section');
    const otherDiv = document.getElementById('other_category_div');
    const simplePriceSection = document.getElementById('simple_price_section');
    const suggestionContainer = document.getElementById('size_suggestions_container');
    const suggestionButtons = document.getElementById('suggestion_buttons');
    const stocksInput = document.getElementById('stocks');

    //Reset Everything
    attrSection.classList.add('d-none');
    otherDiv.classList.add('d-none');
    suggestionContainer.classList.add('d-none');
    stocksInput.readOnly = false; // Default to manual entry for simple items

    //Show Attributes for specific categories
    const showVariantsFor = ['Clothes', 'Clothing', 'Shoes', 'Footwear', 'Gadgets', 'Electronics', 'Furniture'];

    if (showVariantsFor.includes(selectedText)) {
        attrSection.classList.remove('d-none');
        simplePriceSection.classList.add('d-none');
        stocksInput.readOnly = true;
    } else {
        attrSection.classList.add('d-none');
        simplePriceSection.classList.remove('d-none');
        stocksInput.readOnly = false;
    }
    //Handle Size Suggestions
    if (window.sizePresets[selectedText]) {
        suggestionContainer.classList.remove('d-none');
        suggestionButtons.innerHTML = '';
        window.sizePresets[selectedText].forEach(size => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-outline-success btn-sm rounded-pill px-3 suggestion-btn';
            btn.innerText = size;
            btn.onclick = () => document.getElementById('variant_name').value = size;
            suggestionButtons.appendChild(btn);
        });
    }
    if (selectElement.value === 'other') {
        otherDiv.classList.remove('d-none');
    }
}



// --- VARIANT MANAGEMENT ---
function addVariant() {
    const nameInput = document.getElementById('variant_name');
    const stockInput = document.getElementById('variant_stock');
    const listContainer = document.getElementById('variant_list');
    const priceInput = document.getElementById('variant_price');

    if (!nameInput.value || !stockInput.value) {
        alert("Please provide both name and stock for the variant.");
        return;
    }

    const variant = { name: nameInput.value, stock: parseInt(stockInput.value), price: parseFloat(priceInput.value) || 0 };
    productVariants.push(variant);

    const div = document.createElement('div');
    div.className = "variant-card d-flex justify-content-between align-items-center p-2 mb-2 rounded shadow-sm";
    div.innerHTML = `
                <span class="small fw-bold text-dark">${variant.name} <span class="badge bg-secondary ms-2">${variant.stock} in stock</span></span>
                <button type="button" class="btn-close" style="font-size: 0.6rem;" onclick="removeVariant(this, '${variant.name}')"></button>
            `;
    listContainer.appendChild(div);

    nameInput.value = '';
    stockInput.value = '';
    priceInput.value = '';
    updateTotalStock();
}

function removeVariant(btn, name) {
    productVariants = productVariants.filter(v => v.name !== name);
    btn.parentElement.remove();
    updateTotalStock();
}

function updateTotalStock() {
    const total = productVariants.reduce((sum, v) => sum + v.stock, 0);
    document.getElementById('stocks').value = total;
}
document.addEventListener('input', (e) => {
    if (e.target.classList.contains('is-invalid')) e.target.classList.remove('is-invalid');
});