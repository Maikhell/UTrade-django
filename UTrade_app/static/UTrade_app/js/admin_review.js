/**
 * @param {string} itemId 
 * @param {string} newStatus 
 * @param {string} itemType 
 * @param {string} corUrl
 */
function showUserDetails(firstName, lastName, studentNo, course, section, corUrl) {
    // Basic Identity Info
    document.getElementById('modalTitle').innerText = `Verify: ${firstName} ${lastName}`;
    document.getElementById('modalDesc').innerText = `Student No: ${studentNo}`;
    document.getElementById('modalSeller').innerText = `${firstName} ${lastName}`; // Reuse field for name
    document.getElementById('modalCourse').innerText = course;
    document.getElementById('modalSection').innerText = section;
    
    // Clear unused fields (Price/Category) for user view
    document.getElementById('modalPrice').innerText = "N/A";
    document.getElementById('modalCategory').innerText = "Account Verification";

    // Display the COR File in the image container
    const imgContainer = document.getElementById('modalImageContainer');
    imgContainer.innerHTML = '';

    if (corUrl && corUrl !== "None") {
        if (corUrl.toLowerCase().endsWith('.pdf')) {
            // If it's a PDF, provide a link/embed
            imgContainer.innerHTML = `
                <div class="alert alert-info small">This user uploaded a PDF COR.</div>
                <a href="${corUrl}" target="_blank" class="btn btn-outline-primary w-100 mb-3">
                    <i class="bi bi-file-earmark-pdf"></i> View PDF COR
                </a>`;
        } else {
            // If it's an image
            const img = document.createElement('img');
            img.src = corUrl;
            img.className = 'img-fluid rounded-3 shadow-sm mb-2 border';
            imgContainer.appendChild(img);
        }
    } else {
        imgContainer.innerHTML = '<div class="alert alert-danger">No COR file uploaded.</div>';
    }

    // Update Variant List area to show verification warning
    const varContainer = document.getElementById('modalVariantList');
    varContainer.innerHTML = `
        <div class="p-3 mb-2 bg-light border border-warning rounded-2 small">
            <h6 class="fw-bold text-danger"><i class="bi bi-shield-exclamation"></i> Verification Audit</h6>
            <p class="mb-0">Please cross-reference the <strong>Student Number (${studentNo})</strong> with the uploaded COR image.</p>
        </div>
    `;

    // Show the modal
    const myModal = new bootstrap.Modal(document.getElementById('productModal'));
    myModal.show();
}
async function updateStatus(itemId, newStatus, itemType) {
    const csrfElement = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!csrfElement) {
        console.error("CSRF Token not found! Make sure {% csrf_token %} is in your template.");
        Swal.fire('Error', 'Security token missing. Please refresh.', 'error');
        return;
    }

    const csrftoken = csrfElement.value;

    const result = await Swal.fire({
        title: `Confirm ${newStatus}?`,
        text: `Are you sure you want to mark this ${itemType} as ${newStatus}?`,
        icon: newStatus === 'Approved' ? 'success' : 'warning',
        showCancelButton: true,
        confirmButtonColor: newStatus === 'Approved' ? '#198754' : '#dc3545',
        confirmButtonText: 'Confirm'
    });

    if (result.isConfirmed) {
        try {
            let url = `/review/update/${itemType}/${itemId}/`;

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    status: newStatus,
                })
            });

            // ✅ FIX: Handle non-JSON responses (like 404 or login page)
            if (!response.ok) {
                const text = await response.text();
                console.error("Server returned (non-OK):", text);

                Swal.fire('Error', 'Server error. Check console.', 'error');
                return;
            }

            let data;
            try {
                data = await response.json();
            } catch (err) {
                const text = await response.text();
                console.error("Invalid JSON response:", text);
                Swal.fire('Error', 'Invalid server response.', 'error');
                return;
            }

            if (data.status === 'success') {
                const row = document.getElementById(`review-row-${itemId}`);
                if (row) {
                    row.style.transition = '0.4s ease-in-out';
                    row.style.opacity = '0';
                    row.style.transform = 'translateX(50px)';

                    setTimeout(() => {
                        row.remove();

                        const currentTab = document.querySelector('.tab-pane.active');
                        const remaining = currentTab.querySelectorAll('[id^="review-row-"]');

                        if (remaining.length === 0) {
                            location.reload();
                        }
                    }, 400);
                }

                Swal.fire({
                    toast: true,
                    position: 'top-end',
                    icon: 'success',
                    title: `${itemType.charAt(0).toUpperCase() + itemType.slice(1)} ${newStatus}`,
                    showConfirmButton: false,
                    timer: 2000
                });
            } else {
                Swal.fire('Error', data.message || 'Update failed.', 'error');
            }

        } catch (error) {
            console.error("Update Error:", error);
            Swal.fire('Error', 'Could not update status.', 'error');
        }
    }
}

/**
 * @param {Object} extra - Object containing {type: 'product'|'service', leadTime: '', location: ''}
 */
function showDetails(name, desc, seller, course, section, priceRange, category, imageUrls, variants = [], sellerImageUrl = "", extra = {}) {
    // Basic Info
    document.getElementById('modalTitle').innerText = name;
    document.getElementById('modalDesc').innerText = desc;
    document.getElementById('modalSeller').innerText = seller;
    document.getElementById('modalCourse').innerText = course;
    document.getElementById('modalSection').innerText = section;
    document.getElementById('modalPrice').innerText = '₱' + priceRange;
    document.getElementById('modalCategory').innerText = category;

    // Seller Image
    const sellerImg = document.getElementById('modalSellerImage');
    const sellerPlaceholder = document.getElementById('modalSellerPlaceholder');

    if (sellerImageUrl && sellerImageUrl !== "None" && sellerImageUrl !== "") {
        sellerImg.src = sellerImageUrl;
        sellerImg.style.display = 'block';
        sellerPlaceholder.style.display = 'none';
    } else {
        sellerImg.style.display = 'none';
        sellerPlaceholder.style.display = 'flex';
    }

    // Image Gallery
    const imgContainer = document.getElementById('modalImageContainer');
    imgContainer.innerHTML = '';

    imageUrls.forEach(url => {
        if (url) {
            const img = document.createElement('img');
            img.src = url;
            img.className = 'img-fluid rounded-3 shadow-sm mb-2 border';
            imgContainer.appendChild(img);
        }
    });

    // Variants / Service Info
    const varContainer = document.getElementById('modalVariantList');
    varContainer.innerHTML = '';

    if (extra.type === 'service') {
        varContainer.innerHTML = `
            <div class="p-2 mb-2 bg-white border rounded-2 small">
                <div class="d-flex justify-content-between">
                    <span class="text-muted">Lead Time:</span>
                    <span class="fw-bold">${extra.leadTime || 'N/A'}</span>
                </div>
                <div class="d-flex justify-content-between mt-1">
                    <span class="text-muted">Location/Contact:</span>
                    <span class="fw-bold text-primary">${extra.location || 'Digital'}</span>
                </div>
            </div>
        `;
    } else {
        variants.forEach(v => {
            const varDiv = document.createElement('div');
            varDiv.className = 'd-flex justify-content-between align-items-center p-2 mb-1 bg-white border rounded-2 small';
            varDiv.innerHTML = `
                <span class="fw-medium">${v.name}</span>
                <span>
                    <span class="text-success fw-bold">₱${v.price}</span> 
                    <span class="text-muted ms-2">Stock: ${v.stock}</span>
                </span>`;
            varContainer.appendChild(varDiv);
        });
    }
}

function prepareModalData(type, id) {
    console.log(`Preparing modal for ${type} with ID: ${id}`);

    const myModal = new bootstrap.Modal(document.getElementById('productModal'));
    myModal.show();
}