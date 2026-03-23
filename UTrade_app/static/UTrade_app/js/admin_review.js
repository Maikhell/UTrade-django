async function updateStatus(productId, newStatus) {
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    // Configures the confirmation dialog based on Approval or Rejection
    const result = await Swal.fire({
        title: `Confirm ${newStatus}?`,
        text: `Are you sure you want to mark this item as ${newStatus}?`,
        icon: newStatus === 'Approved' ? 'success' : 'warning',
        showCancelButton: true,
        confirmButtonColor: newStatus === 'Approved' ? '#198754' : '#dc3545',
        confirmButtonText: 'Confirm'
    });

    if (result.isConfirmed) {
        try {
            const response = await fetch(`/product-review/update/${productId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ status: newStatus })
            });

            const data = await response.json();

            if (data.status === 'success') {
                // Smooth slide-out animation
                const row = document.getElementById(`review-row-${productId}`);
                if (row) {
                    row.style.transition = '0.4s ease-in-out';
                    row.style.opacity = '0';
                    row.style.transform = 'translateX(50px)';
                    
                    setTimeout(() => {
                        row.remove();
                        // Check if list is now empty to show "All Caught Up" state
                        const remaining = document.querySelectorAll('[id^="review-row-"]');
                        if (remaining.length === 0) {
                            location.reload(); 
                        }
                    }, 400);
                }

                Swal.fire({
                    toast: true,
                    position: 'top-end',
                    icon: 'success',
                    title: `Item ${newStatus}`,
                    showConfirmButton: false,
                    timer: 2000
                });
            }
        } catch (error) {
            console.error("Update Error:", error);
            Swal.fire('Error', 'Could not update status.', 'error');
        }
    }
}

/**
 * Enhanced showDetails to handle Product Variants and Seller Image
 * @param {string} sellerImageUrl - URL of the seller's profile picture
 */
function showDetails(name, desc, seller, course, section, priceRange, category, imageUrls, variants = [], sellerImageUrl = "") {
    // Basic Info Mapping
    document.getElementById('modalTitle').innerText = name;
    document.getElementById('modalDesc').innerText = desc;
    document.getElementById('modalSeller').innerText = seller;
    document.getElementById('modalCourse').innerText = course;
    document.getElementById('modalSection').innerText = section;
    
    // Price displays the range string from our model property
    document.getElementById('modalPrice').innerText = '₱' + priceRange;
    document.getElementById('modalCategory').innerText = category;

    // --- Seller Image Logic ---
    const sellerImg = document.getElementById('modalSellerImage');
    const sellerPlaceholder = document.getElementById('modalSellerPlaceholder');

   if (sellerImageUrl && sellerImageUrl !== "" && sellerImageUrl !== "None") {
        // Show Image
        sellerImg.src = sellerImageUrl;
        sellerImg.style.display = 'block';
        
        // Hide Placeholder by removing the flex display class
        sellerPlaceholder.classList.remove('d-flex');
        sellerPlaceholder.style.display = 'none';
    } else {
        // Hide Image
        sellerImg.style.display = 'none';
        
        // Show Placeholder by adding the flex display class back
        sellerPlaceholder.classList.add('d-flex');
        sellerPlaceholder.style.display = 'flex';
    }
    
    // --- Product Image Gallery Logic ---
    const imgContainer = document.getElementById('modalImageContainer');
    imgContainer.innerHTML = ''; 

    if (imageUrls && imageUrls.length > 0 && imageUrls[0] !== "") {
        imageUrls.forEach(url => {
            const img = document.createElement('img');
            img.src = url;
            img.className = 'img-fluid rounded-3 shadow-sm mb-2';
            img.style.border = '1px solid #eee';
            img.loading = 'lazy';
            imgContainer.appendChild(img);
        });
    } else {
        imgContainer.innerHTML = `
            <div class="text-center p-5 bg-light rounded-3 text-muted">
                <i class="bi bi-image fs-1"></i>
                <p class="small mb-0">No images uploaded</p>
            </div>`;
    }

    // --- Variant & Stock Logic ---
    const varContainer = document.getElementById('modalVariantList');
    if (varContainer) {
        varContainer.innerHTML = '';
        if (variants && variants.length > 0) {
            variants.forEach(v => {
                const varDiv = document.createElement('div');
                varDiv.className = 'd-flex justify-content-between align-items-center p-2 mb-1 bg-white border rounded-2 small';
                varDiv.innerHTML = `
                    <span class="fw-medium">${v.name}</span>
                    <span>
                        <span class="text-success fw-bold">₱${v.price}</span> 
                        <span class="text-muted ms-2">Stock: ${v.stock}</span>
                    </span>
                `;
                varContainer.appendChild(varDiv);
            });
        } else {
            varContainer.innerHTML = '<p class="text-muted small italic">No specific variants listed.</p>';
        }
    }
}