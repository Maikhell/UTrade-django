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