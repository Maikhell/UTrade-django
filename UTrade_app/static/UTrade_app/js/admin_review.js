async function updateStatus(productId, newStatus) {
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
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
                const row = document.getElementById(`review-row-${productId}`);
                row.style.transition = '0.4s';
                row.style.opacity = '0';
                row.style.transform = 'translateX(50px)';
                setTimeout(() => row.remove(), 400);

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
            Swal.fire('Error', 'Could not update status.', 'error');
        }
    }
}
function showDetails(name, desc, seller, course, section, price, category, imageUrls) {
    // Basic Info
    document.getElementById('modalTitle').innerText = name;
    document.getElementById('modalDesc').innerText = desc;
    document.getElementById('modalSeller').innerText = seller;
    document.getElementById('modalCourse').innerText = course;
    document.getElementById('modalSection').innerText = section;
    document.getElementById('modalPrice').innerText = '₱' + price;
    document.getElementById('modalCategory').innerText = category;

    // Image Gallery Logic
    const container = document.getElementById('modalImageContainer');
    container.innerHTML = ''; // Clear previous images

    if (imageUrls.length > 0 && imageUrls[0] !== "") {
        imageUrls.forEach(url => {
            const img = document.createElement('img');
            img.src = url;
            img.className = 'img-fluid rounded-3 shadow-sm mb-2';
            img.style.border = '1px solid #eee';
            container.appendChild(img);
        });
    } else {
        container.innerHTML = '<div class="text-center p-5 bg-light rounded-3"><i class="bi bi-camera-video-off fs-1 text-muted"></i><p class="small">No images uploaded</p></div>';
    }
}