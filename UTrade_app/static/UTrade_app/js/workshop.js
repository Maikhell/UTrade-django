if (typeof window.itemCount === 'undefined') {
    window.itemCount = 0;
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
async function addToStaging() {
    // 1. Elements
    const nameEl = document.getElementById('name');
    const priceEl = document.getElementById('price');
    const stocksEl = document.getElementById('stocks');
    const descEl = document.getElementById('description');
    const categoryEl = document.getElementById('category');
    const preOrderElement = document.getElementById('is_pre_order');
    const locSelect = document.getElementById('location_select');
    const finalLocationsInput = document.getElementById('final_locations');
    const ownerTypeEl = document.getElementById('owner_type');
    const attributesSection = document.getElementById('attributes_section');

    const isVariantMode = attributesSection && !attributesSection.classList.contains('d-none');
    
    [nameEl, priceEl, stocksEl].forEach(el => el && el.classList.remove('is-invalid'));
    let hasError = false;

    // 2. Validation
    if (locSelect) finalLocationsInput.value = locSelect.value;

    if (!finalLocationsInput || !finalLocationsInput.value.trim()) {
        return Swal.fire('Location Required', 'Please select at least one campus meetup spot.', 'warning');
    }
    if (!nameEl.value.trim()) {
        nameEl.classList.add('is-invalid');
        hasError = true;
    }

    if (checkProhibitedContent(nameEl.value) || checkProhibitedContent(descEl.value)) {
        return Swal.fire('Prohibited Content', 'Your text contains restricted words.', 'error');
    }

    let finalPrice, finalStocks;
    if (isVariantMode) {
        if (productVariants.length === 0) {
            return Swal.fire('Variations Required', 'Please add at least one variety.', 'warning');
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
        return Swal.fire('Photos Required', 'Please select at least one photo.', 'warning');
    }

    if (hasError) return Swal.fire('Required Fields', 'Please fill in the highlighted fields.', 'error');

    // 3. Category Formatting (UPDATED)
    let categoryId = categoryEl.value;
    let categoryName = "Uncategorized";
    let customCategoryName = ""; // To pass explicitly to backend

    if (categoryEl.selectedIndex >= 0) {
        categoryName = categoryEl.options[categoryEl.selectedIndex].text;
    }

    if (categoryId === 'other') {
        customCategoryName = document.getElementById('custom_category')?.value.trim() || "";
        categoryName = customCategoryName || "New Category";
    }

    // 4. Prepare FormData
    const formData = new FormData();
    formData.append('name', nameEl.value);
    formData.append('description', descEl.value);
    formData.append('category', categoryId); // Will be 'other' or a numeric ID
    formData.append('custom_category_name', customCategoryName); // Handle creation on backend
    formData.append('location_options', finalLocationsInput.value);
    formData.append('owner_type', ownerTypeEl?.value || 'PERSONAL');
    
    const paymentEl = document.querySelector('input[name="payment"]:checked');
    formData.append('payment', paymentEl ? paymentEl.value : 'BOTH');
    formData.append('pre_order', preOrderElement ? preOrderElement.value : "False");
    formData.append('variants', JSON.stringify(productVariants));

    selectedFiles.forEach((file) => {
        formData.append('images', file);
    });

    // 5. AJAX CALL
    Swal.fire({
        title: 'Saving to Staging...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
    });

    try {
        const response = await fetch('/api/staged-product/add/', { 
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: formData
        });

        const result = await response.json();

        if (result.status !== 'success') {
            throw new Error(result.message || 'Server error.');
        }

        const dbId = result.staged_id;
        
        // 6. UI Update
        const firstImg = document.querySelector('#image_preview_container img');
        const imageHtml = firstImg 
            ? `<img src="${firstImg.src}" class="rounded shadow-sm me-3" style="width: 70px; height: 70px; object-fit: cover; border: 1px solid #dee2e6;">`
            : `<div class="bg-light rounded me-3 d-flex align-items-center justify-content-center" style="width: 70px; height: 70px; border: 1px solid #dee2e6;"><i class="bi bi-image text-muted"></i></div>`;

        const itemCard = `
        <div class="card staged-item mb-3 p-3 bg-white border-0 shadow-sm animate__animated animate__fadeInRight" data-id="${dbId}">
            <div class="d-flex align-items-start mb-2">
                ${imageHtml}
                <div class="flex-grow-1">
                    <div class="d-flex justify-content-between">
                        <h6 class="mb-0 fw-bold text-dark">${nameEl.value}</h6>
                        <div class="d-flex flex-column gap-2">
                            <button class="btn btn-sm text-danger p-0" onclick="removeItem(this, ${dbId})">
                                <i class="bi bi-trash-fill"></i>
                            </button>
                            <button class="btn btn-sm text-primary p-0" onclick="editItem(${dbId})">
                                <i class="bi bi-pencil-square"></i>
                            </button>
                        </div>
                    </div>
                    <div class="mt-1">
                        <span class="badge bg-success-subtle text-success small">₱${finalPrice}</span>
                        <span class="text-muted small ms-1">Stock: ${finalStocks}</span>
                    </div>
                </div>
            </div>
            <div class="small text-muted mb-2 text-truncate-2" style="font-size: 0.85rem;">${descEl.value}</div>
            <div class="d-flex flex-wrap gap-1 mb-2">
                <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-tag me-1"></i>${categoryName}</span>
                <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-geo-alt me-1"></i>${finalLocationsInput.value}</span>
            </div>
        </div>`;

        const stagingArea = document.getElementById('staging_area');
        if (stagingArea.querySelector('.empty-msg')) stagingArea.innerHTML = '';
        stagingArea.insertAdjacentHTML('afterbegin', itemCard);

        document.getElementById('item_count').innerText = document.querySelectorAll('.staged-item').length;

        // 7. Cleanup
        document.getElementById('product_form').reset();
        window.selectedFiles = [];
        window.productVariants = [];
        window.locationTags = [];
        document.getElementById('image_preview_container').innerHTML = `<div class="text-center py-5 text-muted small w-100">Item added successfully.</div>`;
        document.getElementById('variant_list').innerHTML = '';
        
        if (categoryEl) {
            categoryEl.value = "";
            // Trigger dynamic reset of size/variation sections
            if(typeof handleCategoryChange === "function") handleCategoryChange(categoryEl);
        }

        Swal.fire({
            toast: true,
            position: 'top-end',
            icon: 'success',
            title: 'Saved to Staging List',
            showConfirmButton: false,
            timer: 2000
        });

    } catch (error) {
        console.error("Staging Error:", error);
        Swal.fire('Error', error.message || 'Failed to connect to server.', 'error');
    }
}
async function editItem(stagedId) {
    try {
        const response = await fetch(`/api/staged-product/${stagedId}/`);
        const data = await response.json();

        if (data.error) throw new Error(data.error);

        // 1. Basic Information
        document.getElementById('name').value = data.name;
        document.getElementById('description').value = data.description;
        
        // 2. Category & Custom Category Logic
        const categorySelect = document.getElementById('category');
        const customCategoryDiv = document.getElementById('other_category_div');
        const customCategoryInput = document.getElementById('custom_category');
        
        // Check if the saved category ID exists in our current dropdown
        const optionExists = Array.from(categorySelect.options).some(opt => opt.value == data.category);

        if (optionExists) {
            categorySelect.value = data.category;
            if (customCategoryDiv) customCategoryDiv.classList.add('d-none');
        } else {
            // If it's a custom category from a previous entry, select "other"
            categorySelect.value = 'other';
            if (customCategoryDiv) {
                customCategoryDiv.classList.remove('d-none');
                if (customCategoryInput) customCategoryInput.value = data.category_name || ""; 
            }
        }

        // Trigger dynamic UI logic (like fetching attributes/sizes for this category)
        if (typeof handleCategoryChange === "function") {
            handleCategoryChange(categorySelect);
        }

        // 3. Location Logic
        const locs = data.locations.split(',').map(l => l.trim());
        document.querySelectorAll('.location-checkbox').forEach(cb => {
            cb.checked = locs.includes(cb.value);
        });
        document.getElementById('final_locations').value = data.locations;

        // 4. Image Previews
        const container = document.getElementById('image_preview_container');
        container.innerHTML = '';
        data.images.forEach(img => {
            container.insertAdjacentHTML('beforeend', `
                <div class="preview-wrapper">
                    <img src="${img.url}" class="preview-box ${img.is_main ? 'is-main-image' : ''}">
                </div>
            `);
        });

        // 5. Variants Logic
        window.productVariants = data.variants.map(v => ({
            name: v.variant_name,
            price: v.price,
            stock: v.stocks,
            condition: v.condition
        }));
        
        if (typeof renderVariantList === "function") {
            renderVariantList(); 
        }

        await fetch(`/api/staged-product/delete/${stagedId}/`, { 
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        });
        
        // Update the UI count and remove the card
        const card = document.querySelector(`.staged-item[data-id="${stagedId}"]`);
        if (card) card.remove();
        document.getElementById('item_count').innerText = document.querySelectorAll('.staged-item').length;

    } catch (err) {
        console.error("Edit Error:", err);
        Swal.fire('Error', 'Could not retrieve product data.', 'error');
    }
}
function renderEditGallery(files) {
    const container = document.getElementById('image_preview_container');
    container.innerHTML = ''; 
    
    files.forEach((file, index) => {
        const reader = new FileReader();
        reader.onload = function (e) {
            const wrapper = document.createElement('div');
            wrapper.className = 'preview-wrapper animate__animated animate__fadeIn';
            wrapper.innerHTML = `
                <img src="${e.target.result}" class="preview-box ${index === 0 ? 'is-main-image' : ''}">
            `;
            container.appendChild(wrapper);
        };
        reader.readAsDataURL(file);
    });
}
function renderVariantList() {
    const listContainer = document.getElementById('variant_list');
    listContainer.innerHTML = '';

    window.productVariants.forEach(variant => {
        const div = document.createElement('div');
        div.className = "variant-card d-flex align-items-center p-2 mb-2 rounded shadow-sm border bg-white";
        div.innerHTML = `
            <div class="flex-grow-1">
                <div class="d-flex align-items-center">
                    <span class="small fw-bold text-dark">${variant.name}</span>
                    <span class="badge bg-info-subtle text-info ms-2" style="font-size: 0.6rem;">${variant.condition}</span>
                </div>
                <div class="text-muted" style="font-size: 0.7rem;">
                    ₱${variant.price} | Stock: ${variant.stock}
                </div>
            </div>
            <button type="button" class="btn-close" style="font-size: 0.6rem;" onclick="removeVariant(this, '${variant.name}')"></button>
        `;
        listContainer.appendChild(div);
    });
}
async function submitToAdmin() {
    // Get the current count from the UI badge or the list container
    const stagedCount = document.querySelectorAll('.staged-item').length;

    if (stagedCount === 0) {
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

    // Confirmation Dialog
    const confirmation = await Swal.fire({
        title: 'Submit for Authorization?',
        text: `Are you sure you want to send ${stagedCount} item(s) for review?`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#198754',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Yes, submit it!',
        cancelButtonText: 'Wait, let me check'
    });

    if (!confirmation.isConfirmed) return;

    // Show Loading State
    Swal.fire({
        title: 'Sending to Admin...',
        text: 'Moving your items from staging to the authentication queue.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    const formData = new FormData();
    formData.append('action', 'submit_staging'); // Matches the updated view logic
    formData.append('total_products', stagedCount); // Included just as a safety check

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
            
            window.location.href = result.redirect_url || window.location.pathname;
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
    if (!selectElement || selectElement.selectedIndex === -1) {
        const attrSection = document.getElementById('attributes_section');
        const otherDiv = document.getElementById('other_category_div');
        if (attrSection) attrSection.classList.add('d-none');
        if (otherDiv) otherDiv.classList.add('d-none');
        return;
    }

    const selectedOption = selectElement.options[selectElement.selectedIndex];
    const selectedValue = selectElement.value; // This is the ID or 'other'
    const selectedText = selectedOption.text.trim();

    const attrSection = document.getElementById('attributes_section');
    const otherDiv = document.getElementById('other_category_div');
    const simplePriceSection = document.getElementById('simple_price_section');
    const suggestionContainer = document.getElementById('size_suggestions_container');
    const suggestionButtons = document.getElementById('suggestion_buttons');
    const stocksInput = document.getElementById('stocks');
    const noAttributesNote = document.getElementById('no_attributes_note');

    // Reset default UI state
    attrSection.classList.add('d-none');
    otherDiv.classList.add('d-none');
    suggestionContainer.classList.add('d-none');
    if (noAttributesNote) noAttributesNote.classList.add('d-none');
    if (simplePriceSection) simplePriceSection.classList.remove('d-none');
    if (stocksInput) stocksInput.readOnly = false;

    // 1. Handle "Other" Selection
    if (selectedValue === 'other') {
        otherDiv.classList.remove('d-none');
        attrSection.classList.remove('d-none'); // Show variants area so they can type
        if (noAttributesNote) noAttributesNote.classList.remove('d-none');
        if (simplePriceSection) simplePriceSection.classList.add('d-none');
        if (stocksInput) stocksInput.readOnly = true;
        return; // Stop execution here for "Other"
    }

    // 2. Fetch Attributes from Database
    fetch(`/api/get-attributes/${selectedValue}/`)
        .then(response => response.json())
        .then(data => {
            // If the database has attributes, treat it as a variant-based product
            if (data.attributes && data.attributes.length > 0) {
                attrSection.classList.remove('d-none');
                suggestionContainer.classList.remove('d-none');
                if (simplePriceSection) simplePriceSection.classList.add('d-none');
                if (stocksInput) stocksInput.readOnly = true;

                suggestionButtons.innerHTML = '';
                data.attributes.forEach(attr => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'btn btn-outline-success btn-sm rounded-pill px-3 suggestion-btn me-2 mb-2';
                    btn.innerText = attr.value;
                    btn.onclick = function () {
                        const variantInput = document.getElementById('variant_name');
                        if (variantInput) {
                            variantInput.value = attr.value;
                            variantInput.focus();
                        }
                    };
                    suggestionButtons.appendChild(btn);
                });
            } else {
                // If no attributes found in DB, it remains a simple product unless it's a known variant category
                const showVariantsFor = ['Clothes', 'Clothing', 'Shoes', 'Footwear', 'Gadgets', 'Electronics', 'Furniture', 'Watches'];
                if (showVariantsFor.includes(selectedText)) {
                    attrSection.classList.remove('d-none');
                    if (simplePriceSection) simplePriceSection.classList.add('d-none');
                    if (stocksInput) stocksInput.readOnly = true;
                }
            }
        })
        .catch(err => {
            console.error('Error fetching attributes:', err);
        });
}
function addVariant() {
    // Correct IDs based on your specific HTML structure
    const nameInput = document.getElementById('variant_name');
    const priceInput = document.getElementById('variant_price');
    const stockInput = document.getElementById('variant_stock');
    const attrInput = document.getElementById('variant_attribute'); // The strictly separated attribute
    const flawsInput = document.getElementById('variant_flaws');
    const conditionSelect = document.getElementById('variant_condition');
    const listContainer = document.getElementById('variant_list');

    // 1. Data Capture & Case-Sensitive Logic
    const variantName = nameInput.value.trim();
    const variantAttr = attrInput.value.trim();
    const stockValue = stockInput.value;

    // 2. Strict Validation
    if (!variantName || !variantAttr || !stockValue) {
        Swal.fire('Missing Info', "Please provide a Variant Name, Attribute (e.g. XL), and Stock.", 'warning');
        return;
    }

    // Optional: Case-sensitive check against existing suggestions
    document.querySelectorAll('#suggestion_buttons .btn').forEach(btn => {
        if (btn.innerText === variantAttr) {
            console.log("Matching category attribute found:", btn.innerText);
        }
    });

    // 3. Gathering Remaining Data
    const priceValue = parseFloat(priceInput.value) || 0;
    const conditionValue = conditionSelect ? conditionSelect.value : 'Brand New';
    const flawsValue = flawsInput ? flawsInput.value.trim() : '';

    const variant = {
        name: variantName,
        price: priceValue,
        stock: parseInt(stockValue),
        attribute: variantAttr, // Separated attribute for category linking
        condition: conditionValue,
        flaws: flawsValue,
        imageIndex: currentSelectedImageIndex
    };

    // 4. UI Rendering (Using the separate name and attribute)
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
                <span class="badge bg-secondary-subtle text-secondary ms-2" style="font-size: 0.6rem;">${variant.attribute}</span>
                <span class="badge bg-info-subtle text-info ms-1" style="font-size: 0.6rem;">${variant.condition}</span>
            </div>
            <div class="text-muted" style="font-size: 0.7rem;">
                ₱${variant.price.toFixed(2)} | Stock: ${variant.stock}
                ${variant.flaws ? ` | <span class="text-danger">Flaw: ${variant.flaws}</span>` : ''}
            </div>
        </div>
        <button type="button" class="btn-close" style="font-size: 0.6rem;" onclick="removeVariant(this, '${variant.name}')"></button>
    `;
    listContainer.appendChild(div);

    // 5. Reset Fields (Back to Original Structure)
    nameInput.value = '';
    attrInput.value = '';
    priceInput.value = '';
    stockInput.value = '';
    if (flawsInput) flawsInput.value = '';
    if (conditionSelect) conditionSelect.value = 'Brand New';

    // Reset Image Picker UI
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
function updateHiddenLocation() {
    const select = document.getElementById('location_select');
    const hiddenInput = document.getElementById('final_locations');
    hiddenInput.value = select.value;
}
function updateMultiLocations() {
    const checkboxes = document.querySelectorAll('.location-checkbox:checked');
    const selectedLocations = Array.from(checkboxes).map(cb => cb.value);

    const hiddenInput = document.getElementById('final_locations');
    hiddenInput.value = selectedLocations.join(', ');

    console.log("Selected Locations:", hiddenInput.value);
}

function useCustomAttribute() {
    const input = document.getElementById('custom_attribute_input');
    const val = input.value.trim();
    if (!val) return;

    // Case-sensitive check against existing suggestion buttons
    let exists = false;
    document.querySelectorAll('#suggestion_buttons .btn').forEach(btn => {
        if (btn.innerText === val) { // Strict case-sensitive comparison
            exists = true;
            btn.click(); // If it exists, just select it
        }
    });

    if (!exists) {
        // If it doesn't exist, set it as the variant name automatically
        document.getElementById('variant_name').value = val;
        input.value = ''; // clear input
    }
}