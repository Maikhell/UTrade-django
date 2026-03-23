if (typeof itemCount === 'undefined') {
    // Initialize global state only if not already defined to prevent script collision
    var itemCount = 0;
    var currentAttributes = { sizes: [], varieties: [], colors: [] };
    var selectedFiles = [];
    var allStagedServices = [];
    console.log("Services script initialized.");
}

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
            const badge = isMain ? '<span class="main-badge">Cover</span>' : '';
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

function addToStaging() {
    const name = document.getElementById('name').value;
    const price = document.getElementById('price').value;
    const stocks = document.getElementById('stocks').value;
    const desc = document.getElementById('description').value;
    const categoryEl = document.getElementById('category');
    const categoryName = categoryEl.options[categoryEl.selectedIndex].text;
    const categoryId = categoryEl.value;
    const delivery = document.getElementById('condition').value;
    const leadTime = document.getElementById('meetup').value;

    const serviceId = Date.now();
    const paymentEl = document.querySelector('input[name="payment"]:checked');
    const payment = paymentEl ? paymentEl.value : 'Not Specified';

    if (!name || !price || !leadTime) return alert('Please fill in Title, Price, and Lead Time!');

    const stagingArea = document.getElementById('staging_area');
    const firstImagePreview = document.querySelector('#image_preview_container img');
    const firstImageSrc = firstImagePreview ? firstImagePreview.src : null;

    // Capture current form state into an object and store it in the staging array
    const serviceData = {
        id: serviceId,
        name: name,
        price: price,
        stocks: stocks,
        description: desc,
        category: categoryId,
        delivery: delivery,
        leadTime: leadTime,
        payment: payment,
        files: [...selectedFiles]
    };

    allStagedServices.push(serviceData);
    itemCount = allStagedServices.length;
    document.getElementById('item_count').innerText = itemCount;

    if (stagingArea.querySelector('.empty-msg')) stagingArea.innerHTML = '';

    // Generate dynamic HTML for the staging card including a fallback icon if no image is uploaded
    const imageHtml = firstImageSrc
        ? `<img src="${firstImageSrc}" class="rounded shadow-sm me-3" style="width: 70px; height: 70px; object-fit: cover; border: 1px solid #dee2e6;">`
        : `<div class="bg-light rounded me-3 d-flex align-items-center justify-content-center" style="width: 70px; height: 70px; border: 1px solid #dee2e6;"><i class="bi bi-tools text-muted"></i></div>`;

    const itemCard = `
        <div class="card staged-item mb-3 p-3 bg-white border-0 shadow-sm animate__animated animate__fadeInRight" data-id="${serviceId}">
            <div class="d-flex align-items-start mb-2">
                ${imageHtml}
                <div class="flex-grow-1">
                    <div class="d-flex justify-content-between">
                        <h6 class="mb-0 fw-bold text-dark">${name}</h6>
                        <button class="btn btn-sm text-danger p-0" onclick="removeItem(this, ${serviceId})">
                            <i class="bi bi-trash-fill"></i>
                        </button>
                    </div>
                    <div class="mt-1">
                        <span class="badge bg-success-subtle text-success small">₱${price}</span>
                        <span class="text-muted small ms-1">${leadTime}</span>
                    </div>
                </div>
            </div>
            <div class="small text-muted mb-2 text-truncate-2">${desc}</div>
            <div class="d-flex flex-wrap gap-1">
                <span class="badge bg-light text-dark border fw-normal">${categoryName}</span>
                <span class="badge bg-info-subtle text-dark border fw-normal">${delivery}</span>
            </div>
        </div>`;

    stagingArea.insertAdjacentHTML('afterbegin', itemCard);
    document.getElementById('product_form').reset();
    selectedFiles = [];
    document.getElementById('image_preview_container').innerHTML = '<div class="text-center py-5 text-muted small w-100">Service added to list.</div>';
}

async function submitToAdmin() {
    if (allStagedServices.length === 0) {
        return Swal.fire({
            icon: 'warning',
            title: 'No Services Added',
            text: 'Please add at least one service to the list before submitting.',
            confirmButtonColor: '#198754'
        });
    }
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    if (!csrftoken) {
        return Swal.fire('Error', 'CSRF Token missing. Please refresh the page.', 'error');
    }
    const confirmation = await Swal.fire({
        title: 'Submit Services?',
        text: `You are about to send ${allStagedServices.length} service(s) for review.`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#198754',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Yes, submit for review',
        cancelButtonText: 'Not yet'
    });

    if (!confirmation.isConfirmed) return;
    Swal.fire({
        title: 'Uploading Services...',
        text: 'This may take a moment depending on your image sizes.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    // Create a flat FormData map to handle multiple services and their respective images in one request
    const formData = new FormData();
    allStagedServices.forEach((service, index) => {
        formData.append(`serv_${index}_name`, service.name);
        formData.append(`serv_${index}_price`, service.price);
        formData.append(`serv_${index}_desc`, service.description);
        formData.append(`serv_${index}_category`, service.category);
        formData.append(`serv_${index}_lead_time`, service.leadTime);
        formData.append(`serv_${index}_delivery`, service.delivery);
        formData.append(`serv_${index}_payment`, service.payment);

        // Iterate through files for each service to append them as individual form fields
        service.files.forEach((file, fileIndex) => {
            formData.append(`serv_${index}_image_${fileIndex}`, file);
        });
        formData.append(`serv_${index}_image_count`, service.files.length);
    });
    formData.append('total_services', allStagedServices.length);
    
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
                text: 'Your services have been submitted for review.',
                confirmButtonColor: '#198754'
            });
            window.location.reload();
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Submission Error',
                text: result.message || 'Something went wrong on the server.'
            });
        }
    } catch (error) {
        console.error("Submission Error:", error);
        Swal.fire({
            icon: 'error',
            title: 'Connection Failed',
            text: 'Could not connect to the server. Please check your internet.'
        });
    }
}

function removeItem(btn, serviceId) {
    btn.closest('.staged-item').remove();
    allStagedServices = allStagedServices.filter(item => item.id !== serviceId);
    itemCount = allStagedServices.length;
    document.getElementById('item_count').innerText = itemCount;
}

function addTag(type) {
    const input = document.getElementById(`${type}_input`);
    const tagContainer = document.getElementById(`${type}_tags`);
    const mainDisplay = document.getElementById('attribute_pills');
    const val = input.value.trim();
    if (!val) return;

    // Prevent duplicate entries by checking the existing attribute array before adding new pills
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

function removeTag(type, value, element) {
    currentAttributes[`${type}s`] = currentAttributes[`${type}s`].filter(val => val !== value);
    element.parentElement.remove();
}