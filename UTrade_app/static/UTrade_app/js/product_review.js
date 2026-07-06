/**
 * UTrade Admin & Review Module
 * Handles moderation actions and detail views for products/services.
 */

// Centralized Configuration / Constants
const CONFIG = {
    CURRENCY_SYMBOL: '₱',
    URLS: {
        updateStatus: (type, id) => `/review/update/${type}/${id}/`
    }
};

/**
 * Display Certificate of Registration (COR) or Officer ID modal
 * @param {string} url - The dynamic source image location
 * @param {string} fallbackText - Alt text if URL is missing
 */
export const displayVerificationImage = (url, fallbackText = 'No image uploaded') => {
    const imageElement = document.getElementById('cor_image');
    if (!imageElement) return console.error('Verification image element container missing from DOM.');

    if (url?.trim()) {
        imageElement.src = url;
        imageElement.alt = 'Verification document';
    } else {
        imageElement.src = '';
        imageElement.alt = fallbackText;
    }

    const modalInstance = new bootstrap.Modal(document.getElementById('corModal'));
    modalInstance.show();
};

/**
 * Process moderation approvals/rejections with asynchronous server sync
 * @param {string|number} itemId 
 * @param {string} newStatus 
 * @param {string} itemType 
 */
export const updateStatus = async (itemId, newStatus, itemType) => {
    const csrfElement = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!csrfElement) {
        Swal.fire('Security Error', 'Token verification mismatch. Please reload.', 'error');
        return;
    }

    const isApproved = newStatus === 'Approved';
    const confirmation = await Swal.fire({
        title: `Confirm ${newStatus}?`,
        text: `Are you sure you want to mark this ${itemType} as ${newStatus}?`,
        icon: isApproved ? 'success' : 'warning',
        showCancelButton: true,
        confirmButtonColor: isApproved ? '#198754' : '#dc3545',
        confirmButtonText: 'Confirm'
    });

    if (!confirmation.isConfirmed) return;

    try {
        const response = await fetch(CONFIG.URLS.updateStatus(itemType, itemId), {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfElement.value,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ status: newStatus })
        });

        if (!response.ok) throw new Error(`Server status returned: ${response.status}`);

        const data = await response.json();

        if (data.status === 'success') {
            animateRowRemoval(itemId);
            triggerToastNotification(`${itemType} marked as ${newStatus}`);
        } else {
            Swal.fire('Process Failed', data.message || 'Update failed.', 'error');
        }

    } catch (error) {
        console.error("Moderation Update Error:", error);
        Swal.fire('Transmission Error', 'Could not sync status changes with server.', 'error');
    }
};

/**
 * Handles smooth element exit animations
 * @param {string|number} itemId 
 */
const animateRowRemoval = (itemId) => {
    const targetRow = document.getElementById(`review-row-${itemId}`);
    if (!targetRow) return;

    targetRow.style.transition = '0.4s ease-in-out';
    targetRow.style.opacity = '0';
    targetRow.style.transform = 'translateX(50px)';

    setTimeout(() => {
        targetRow.remove();
        const activeTab = document.querySelector('.tab-pane.active');
        const itemsRemaining = activeTab?.querySelectorAll('[id^="review-row-"]');
        
        if (itemsRemaining?.length === 0) {
            location.reload();
        }
    }, 400);
};

/**
 * Triggers lightweight top-end feedback alert
 * @param {string} message 
 */
const triggerToastNotification = (message) => {
    Swal.fire({
        toast: true,
        position: 'top-end',
        icon: 'success',
        title: message,
        showConfirmButton: false,
        timer: 2000
    });
};

/**
 * Dynamically updates listing specifications inside review panels
 */
export const showDetails = (name, desc, seller, course, section, priceRange, category, imageUrls, variants = [], sellerImageUrl = "", extra = {}) => {
    document.getElementById('modalTitle').innerText = name;
    document.getElementById('modalDesc').innerText = desc;
    document.getElementById('modalSeller').innerText = seller;
    document.getElementById('modalCourse').innerText = course;
    document.getElementById('modalSection').innerText = section;
    document.getElementById('modalPrice').innerText = `${CONFIG.CURRENCY_SYMBOL}${priceRange}`;
    document.getElementById('modalCategory').innerText = category;

    renderSellerAvatar(sellerImageUrl);
    renderGallery(imageUrls);
    renderMetadataOrVariants(extra, variants);
};

const renderSellerAvatar = (url) => {
    const avatarImg = document.getElementById('modalSellerImage');
    const placeholder = document.getElementById('modalSellerPlaceholder');
    const isValidUrl = url && url !== "None" && url !== "";

    avatarImg.style.display = isValidUrl ? 'block' : 'none';
    placeholder.style.display = isValidUrl ? 'none' : 'flex';
    if (isValidUrl) avatarImg.src = url;
};

const renderGallery = (urls) => {
    const container = document.getElementById('modalImageContainer');
    container.innerHTML = '';
    
    urls.filter(Boolean).forEach(url => {
        const image = document.createElement('img');
        image.src = url;
        image.className = 'img-fluid rounded-3 shadow-sm mb-2 border';
        container.appendChild(image);
    });
};

const renderMetadataOrVariants = (extra, variants) => {
    const listContainer = document.getElementById('modalVariantList');
    listContainer.innerHTML = '';

    if (extra.type === 'service') {
        listContainer.innerHTML = `
            <div class="p-2 mb-2 bg-white border rounded-2 small">
                <div class="d-flex justify-content-between">
                    <span class="text-muted">Lead Time:</span>
                    <span class="fw-bold">${extra.leadTime || 'N/A'}</span>
                </div>
                <div class="d-flex justify-content-between mt-1">
                    <span class="text-muted">Location/Contact:</span>
                    <span class="fw-bold text-primary">${extra.location || 'Digital'}</span>
                </div>
            </div>`;
    } else {
        variants.forEach(v => {
            const variantRow = document.createElement('div');
            variantRow.className = 'd-flex justify-content-between align-items-center p-2 mb-1 bg-white border rounded-2 small';
            variantRow.innerHTML = `
                <span class="fw-medium">${v.name}</span>
                <span>
                    <span class="text-success fw-bold">${CONFIG.CURRENCY_SYMBOL}${v.price}</span> 
                    <span class="text-muted ms-2">Stock: ${v.stock}</span>
                </span>`;
            listContainer.appendChild(variantRow);
        });
    }
};