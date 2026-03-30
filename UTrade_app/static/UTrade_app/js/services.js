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

// ... (Keep your previewMultipleImages function)

function addToStaging() {
    const name = document.getElementById('name').value;
    const price = document.getElementById('price').value;
    const desc = document.getElementById('description').value;
    const categoryEl = document.getElementById('category');
    const categoryId = categoryEl.value;
    const categoryName = categoryEl.options[categoryEl.selectedIndex].text;
    const delivery = document.getElementById('condition').value;
    const leadTime = document.getElementById('meetup').value;
    const payment = document.querySelector('input[name="payment"]:checked')?.value || 'Cash';

    if (!name || !price) return Swal.fire('Error', 'Title and Price are required!', 'error');

    const serviceId = Date.now();

    // Capture the tags from our currentAttributes object
    const serviceData = {
        id: serviceId,
        name: name,
        price: price,
        description: desc,
        category: categoryId,
        delivery: delivery,
        leadTime: leadTime,
        payment: payment,
        attributes: { ...currentAttributes }, // Added tags here
        files: [...selectedFiles]
    };

    allStagedServices.push(serviceData);
    updateStagingUI();

    // Reset form and current tags
    document.getElementById('product_form').reset();
    document.getElementById('attribute_pills').innerHTML = '';
    document.getElementById('image_preview_container').innerHTML = `
    <div class="text-center py-5 text-muted small w-100" style="grid-column: span 2;">
        <i class="bi bi-cloud-arrow-up display-6 d-block mb-2"></i>
        Showcase your next service
    </div>`;
    currentAttributes = { sizes: [], varieties: [], colors: [] };
    selectedFiles = []; 

}
function toggleDeliveryInputs() {
    const deliveryMethod = document.getElementById('condition').value;
    const digitalGroup = document.getElementById('digital_info_group');
    const locationGroup = document.getElementById('location_info_group');

    // Reset visibility
    digitalGroup.style.display = 'none';
    locationGroup.style.display = 'none';

    if (deliveryMethod === 'Digital Only') {
        digitalGroup.style.display = 'block';
    } else if (['Physical Delivery', 'On-Site Service', 'Labor/Gig'].includes(deliveryMethod)) {
        locationGroup.style.display = 'block';
    }
}

// Run once on page load to set initial state
document.addEventListener('DOMContentLoaded', toggleDeliveryInputs);
function updateStagingUI() {
    const stagingArea = document.getElementById('staging_area');
    const itemCountEl = document.getElementById('item_count');
    itemCountEl.innerText = allStagedServices.length;

    if (allStagedServices.length === 0) {
        stagingArea.innerHTML = '<div class="text-center py-5 text-muted empty-msg">No services staged.</div>';
        return;
    }

    stagingArea.innerHTML = allStagedServices.map(service => `
        <div class="card staged-item mb-3 p-3 border-0 shadow-sm animate__animated animate__fadeInRight">
            <div class="d-flex justify-content-between">
                <h6 class="fw-bold mb-1">${service.name}</h6>
                <button class="btn btn-sm text-danger" onclick="removeItem(null, ${service.id})"><i class="bi bi-trash"></i></button>
            </div>
            <div class="small text-success fw-bold">₱${service.price} — ${service.leadTime}</div>
            <div class="mt-2">
                ${service.attributes.sizes.map(s => `<span class="badge bg-light text-dark border me-1">${s}</span>`).join('')}
            </div>
        </div>
    `).join('');
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