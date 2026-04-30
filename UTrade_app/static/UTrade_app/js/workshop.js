if (typeof window.itemCount === 'undefined') {
    window.itemCount = 0;
    window.currentAttributes = { sizes: [], varieties: [], colors: [] };
    window.selectedFiles = [];
    window.allStagedProducts = [];
    window.productVariants = [];
    window.currentSelectedImageIndex = null;
    window.locationTags = [];
    window.PROHIBITED_WORDS = [];
}
async function loadProhibitedWords() {
    try {
        const response = await fetch('/api/prohibited-words/');
        const data = await response.json();
        window.PROHIBITED_WORDS = data.prohibited_words;
        console.log("Prohibited words loaded:", window.PROHIBITED_WORDS.length);
    } catch (error) {
        console.error("Failed to load prohibited words:", error);
        window.PROHIBITED_WORDS = ['scam', 'drugs', 'shabu'];
    }
}
loadProhibitedWords();
window.sizePresets = {
    Clothes: ['S', 'M', 'L', 'XL', 'XXL'],
    Clothing: ['S', 'M', 'L', 'XL', 'XXL'],
    Shoes: ['38', '39', '40', '41', '42', '43', '44'],
    Footwear: ['38', '39', '40', '41', '42', '43', '44'],
    Watches: ['36', '38', '40', '41', '42', '43']
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
        };
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
function toggleOtherCategory(select) {
    const otherDiv = document.getElementById('other_category_div');
    if (select.value === 'other') {
        otherDiv.classList.remove('d-none');
    } else {
        otherDiv.classList.add('d-none');
    }
}
function toggleCustomCondition(select) {
    const customInput = document.getElementById('custom_condition_input');
    if (!customInput) return;
    if (select.value === 'Other') {
        customInput.classList.remove('d-none');
        customInput.focus();
    } else {
        customInput.classList.add('d-none');
    }
}
function addToStaging() {
    const nameEl = document.getElementById('name');
    const priceEl = document.getElementById('price');
    const stocksEl = document.getElementById('stocks');
    const descEl = document.getElementById('description');
    const categoryEl = document.getElementById('category');
    const finalLocationsInput = document.getElementById('final_locations');
    const preOrderElement = document.getElementById('is_pre_order');
    const isVariantMode = !document.getElementById('attributes_section').classList.contains('d-none');
    [nameEl, priceEl, stocksEl].forEach(el => el.classList.remove('is-invalid'));
    let hasError = false;
    if (window.locationTags.length === 0) {
        Swal.fire('Location Required', 'Please add at least one campus meetup spot.', 'warning');
        return;
    }
    if (!nameEl.value.trim()) {
        nameEl.classList.add('is-invalid');
        hasError = true;
    }
    if (checkProhibitedContent(nameEl.value)) {
        Swal.fire('Prohibited Content', 'The product name contains restricted words.', 'error');
        nameEl.classList.add('is-invalid');
        return;
    }
    if (checkProhibitedContent(descEl.value)) {
        Swal.fire('Prohibited Content', 'The description contains restricted words.', 'error');
        descEl.classList.add('is-invalid');
        return;
    }
    if (checkProhibitedContent(window.locationTags.join(' '))) {
        Swal.fire('Prohibited Content', 'One of your meetup locations contains restricted words.', 'error');
        return;
    }
    let finalPrice, finalStocks;
    if (isVariantMode) {
        if (productVariants.length === 0) {
            Swal.fire('Variations Required', 'Please add at least one size or variety using the "Add" button.', 'warning');
            return;
        }
        finalPrice = productVariants[0].price;
        finalStocks = productVariants.reduce((sum, v) => sum + v.stock, 0);
    } else {
        if (!priceEl.value.trim()) { priceEl.classList.add('is-invalid'); hasError = true; }
        if (!stocksEl.value.trim()) { stocksEl.classList.add('is-invalid'); hasError = true; }
        finalPrice = priceEl.value;
        finalStocks = stocksEl.value;
    }
    if (selectedFiles.length === 0) {
        Swal.fire('Photos Required', 'Please select at least one photo for your product.', 'warning');
        return;
    }
    if (hasError) {
        return Swal.fire({
            title: 'Required Fields',
            text: 'Please fill in the red-highlighted fields.',
            icon: 'error',
            confirmButtonColor: '#dc3545'
        });
    }
    let categoryId = categoryEl.value;
    let categoryName = categoryEl.options[categoryEl.selectedIndex].text;
    if (categoryId === 'other') {
        const customValue = document.getElementById('custom_category').value.trim();
        categoryId = `NEW:${customValue}`;
        categoryName = customValue;
    }
    const conditionEl = document.getElementById('variant_condition');
    const globalCondition = conditionEl ? conditionEl.value : "Brand New";
    const isPreOrder = preOrderElement ? preOrderElement.value : "False";
    const productId = Date.now();
    const paymentEl = document.querySelector('input[name="payment"]:checked');
    const payment = paymentEl ? paymentEl.value : 'BOTH';
    const productData = {
        id: productId,
        name: nameEl.value,
        price: finalPrice,
        stocks: finalStocks,
        description: descEl.value,
        category: categoryId,
        pre_order: isPreOrder,
        condition: globalCondition,
        meetup: finalLocationsInput ? finalLocationsInput.value : '',
        payment: payment,
        files: [...selectedFiles],
        variants: [...productVariants],
        owner_type: document.getElementById('owner_type')?.value || 'PERSONAL'
    };
    allStagedProducts.push(productData);
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
                <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-geo-alt me-1"></i>${productData.meetup}</span>
                <span class="badge ${payment === 'GCASH' ? 'bg-primary' : 'bg-success'} text-white fw-normal">
                    <i class="bi bi-wallet2 me-1"></i>${payment}
                </span>
            </div>
        </div>`;
    stagingArea.insertAdjacentHTML('afterbegin', itemCard);
    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 2000,
        timerProgressBar: true
    });
    Toast.fire({
        icon: 'success',
        title: 'Item added to staging list'
    });
    document.getElementById('product_form').reset();
    window.locationTags = [];
    renderLocationTags();
    productVariants = [];
    document.getElementById('variant_list').innerHTML = '';
    const attrPills = document.getElementById('attribute_pills');
    if (attrPills) attrPills.innerHTML = '';
    document.getElementById('image_preview_container').innerHTML = `
        <div class="text-center py-5 text-muted small w-100">
            <i class="bi bi-check-circle-fill text-success d-block mb-2" style="font-size: 2rem;"></i>
            Item added. Ready for next.
        </div>`;
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
        formData.append(`prod_${index}_pre_order`, product.pre_order);
        formData.append(`prod_${index}_owner_type`, product.owner_type);
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
function handleCategoryChange(selectElement) {
    const selectedText = selectElement.options[selectElement.selectedIndex].text.trim();
    const attrSection = document.getElementById('attributes_section');
    const otherDiv = document.getElementById('other_category_div');
    const simplePriceSection = document.getElementById('simple_price_section');
    const suggestionContainer = document.getElementById('size_suggestions_container');
    const suggestionButtons = document.getElementById('suggestion_buttons');
    const stocksInput = document.getElementById('stocks');
    attrSection.classList.add('d-none');
    otherDiv.classList.add('d-none');
    suggestionContainer.classList.add('d-none');
    if (simplePriceSection) simplePriceSection.classList.remove('d-none');
    stocksInput.readOnly = false;
    const showVariantsFor = ['Clothes', 'Clothing', 'Shoes', 'Footwear', 'Gadgets', 'Electronics', 'Furniture', 'Watches'];
    if (showVariantsFor.includes(selectedText)) {
        attrSection.classList.remove('d-none');
        if (simplePriceSection) simplePriceSection.classList.add('d-none');
        stocksInput.readOnly = true;
    }
    if (window.sizePresets && window.sizePresets[selectedText]) {
        suggestionContainer.classList.remove('d-none');
        suggestionButtons.innerHTML = '';
        window.sizePresets[selectedText].forEach(size => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-outline-success btn-sm rounded-pill px-3 suggestion-btn me-2 mb-2';
            btn.innerText = size;
            btn.onclick = function () {
                const variantInput = document.getElementById('variant_name');
                if (variantInput) {
                    variantInput.value = size;
                    variantInput.focus();
                }
            };
            suggestionButtons.appendChild(btn);
        });
    }
    if (selectElement.value === 'other') {
        otherDiv.classList.remove('d-none');
    }
}
function addVariant() {
    const nameInput = document.getElementById('variant_name');
    const stockInput = document.getElementById('variant_stock');
    const priceInput = document.getElementById('variant_price');
    const conditionSelect = document.getElementById('variant_condition');
    const flawsInput = document.getElementById('variant_flaws');
    const customConditionInput = document.getElementById('custom_condition_input');
    const listContainer = document.getElementById('variant_list');
    // Safely handle potentially null elements
    const conditionValue = conditionSelect ? conditionSelect.value : 'Brand New';
    const flawsValue = flawsInput ? flawsInput.value.trim() : '';
    const customConditionValue = customConditionInput ? customConditionInput.value.trim() : '';
    if (!nameInput.value || !stockInput.value) {
        Swal.fire('Missing Info', "Please provide a name and stock.", 'warning');
        return;
    }
    let finalCondition = conditionValue;
    if (finalCondition === 'Other' && customConditionValue) {
        finalCondition = customConditionValue;
    }
    const variant = {
        name: nameInput.value,
        stock: parseInt(stockInput.value),
        price: parseFloat(priceInput.value) || 0,
        condition: finalCondition,
        flaws: flawsValue,
        imageIndex: currentSelectedImageIndex
    };
    productVariants.push(variant);
    const div = document.createElement('div');
    div.className = "variant-card d-flex align-items-center p-2 mb-2 rounded shadow-sm border bg-white animate__animated animate__fadeInUp";
    let thumbHtml = '';
    if (currentSelectedImageIndex !== null && selectedFiles[currentSelectedImageIndex]) {
        const thumbUrl = URL.createObjectURL(selectedFiles[currentSelectedImageIndex]);
        thumbHtml = `<img src="${thumbUrl}" style="width: 35px; height: 35px; object-fit: cover;" class="rounded me-2 border">`;
    }
    div.innerHTML = `
        ${thumbHtml}
        <div class="flex-grow-1">
            <div class="d-flex align-items-center">
                <span class="small fw-bold text-dark">${variant.name}</span>
                <span class="badge bg-info-subtle text-info ms-2" style="font-size: 0.6rem;">${variant.condition}</span>
            </div>
            <div class="text-muted" style="font-size: 0.7rem;">
                ₱${variant.price} | Stock: ${variant.stock}
                ${variant.flaws ? ` | <span class="text-danger">Flaw: ${variant.flaws}</span>` : ''}
            </div>
        </div>
        <button type="button" class="btn-close" style="font-size: 0.6rem;" onclick="removeVariant(this, '${variant.name}')"></button>
    `;
    listContainer.appendChild(div);
    // Reset form fields
    nameInput.value = '';
    stockInput.value = '';
    priceInput.value = '';
    
    if (flawsInput) {
        flawsInput.value = '';
    }
    
    if (conditionSelect) {
        conditionSelect.value = 'Brand New';
    }
    
    if (customConditionInput) {
        customConditionInput.value = '';
        customConditionInput.classList.add('d-none');
    }
    const imgBtn = document.querySelector('[onclick="openVariantImagePicker()"]');
    if (imgBtn) imgBtn.innerHTML = `<i class="bi bi-image me-1"></i> Pick Image`;
    currentSelectedImageIndex = null;
    updateTotalStock();
}
function openVariantImagePicker() {
    if (selectedFiles.length === 0) {
        return Swal.fire('No Photos', 'Please upload product photos first!', 'info');
    }
    let html = '<div class="row g-2">';
    selectedFiles.forEach((file, index) => {
        const url = URL.createObjectURL(file);
        html += `
            <div class="col-4">
                <div class="position-relative">
                    <img src="${url}" class="img-thumbnail cursor-pointer border-2" 
                         onclick="selectVariantImage(${index})" 
                         style="height: 80px; width: 100%; object-fit: cover;">
                    ${index === 0 ? '<span class="badge bg-dark position-absolute top-0 start-0 m-1" style="font-size: 0.5rem;">Cover</span>' : ''}
                </div>
            </div>`;
    });
    html += '</div>';
    Swal.fire({
        title: 'Assign Image to Variant',
        html: html,
        showConfirmButton: false,
        customClass: { popup: 'rounded-4' }
    });
}
function selectVariantImage(index) {
    currentSelectedImageIndex = index;
    const btn = document.querySelector('[onclick="openVariantImagePicker()"]');
    if (btn) btn.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i> Image Selected`;
    Swal.close();
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
document.addEventListener('DOMContentLoaded', () => {
    const locInput = document.getElementById('location_input');
    if (locInput) {
        locInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                addLocationTag();
            }
        });
    }
});
function addLocationTag() {
    const input = document.getElementById('location_input');
    const value = input.value.trim();
    if (value && !window.locationTags.includes(value)) {
        window.locationTags.push(value);
        renderLocationTags();
        input.value = '';
    } else if (window.locationTags.includes(value)) {
        Swal.fire('Duplicate', 'This location is already added.', 'info');
    }
}
function removeLocationTag(index) {
    window.locationTags.splice(index, 1);
    renderLocationTags();
}
function renderLocationTags() {
    const container = document.getElementById('location_tags_container');
    const hiddenInput = document.getElementById('final_locations');
    container.innerHTML = '';
    window.locationTags.forEach((tag, index) => {
        const badge = document.createElement('span');
        badge.className = 'badge bg-success d-flex align-items-center gap-2 px-3 py-2 rounded-pill shadow-sm animate__animated animate__fadeIn';
        badge.style.fontSize = '0.8rem';
        badge.innerHTML = `
            ${tag} 
            <i class="bi bi-x-circle-fill cursor-pointer text-white-50" onclick="removeLocationTag(${index})"></i>
        `;
        container.appendChild(badge);
    });
    hiddenInput.value = window.locationTags.join(', ');
}
function checkProhibitedContent(text) {
    if (!text || window.PROHIBITED_WORDS.length === 0) return false;
    const lowerText = text.toLowerCase();
    return window.PROHIBITED_WORDS.some(word => lowerText.includes(word.toLowerCase()));
}