document.addEventListener('DOMContentLoaded', function () {
    const itemCheckboxes = document.querySelectorAll('.item-checkbox');
    const sellerCheckboxes = document.querySelectorAll('.seller-checkbox');
    const grandTotalDisplay = document.getElementById('grand-total-display');
    const subtotalDisplay = document.getElementById('subtotal-display');
    const selectedCountDisplay = document.getElementById('selected-count');
    const checkoutBtn = document.getElementById('checkout-btn');

    function calculateTotal() {
        let total = 0;
        let count = 0;

        document.querySelectorAll('.cart-item-row').forEach(row => {
            const checkbox = row.querySelector('.item-checkbox');
            if (checkbox.checked) {
                const price = parseFloat(row.getAttribute('data-price'));
                const qty = parseInt(row.getAttribute('data-quantity'));
                total += (price * qty);
                count++;
            }
        });

        const formattedTotal = `₱${total.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
        grandTotalDisplay.innerText = formattedTotal;
        subtotalDisplay.innerText = formattedTotal;
        selectedCountDisplay.innerText = `${count} Items Selected`;

        // Disable checkout if 0 items selected
        if (checkoutBtn) checkoutBtn.classList.toggle('disabled', count === 0);
    }

    // Individual Item Checkbox Logic
    itemCheckboxes.forEach(cb => {
        cb.addEventListener('change', calculateTotal);
    });

    // Seller Checkbox Logic (Selects/Deselects all items from that seller)
    sellerCheckboxes.forEach(scb => {
        scb.addEventListener('change', function () {
            const sellerName = this.getAttribute('data-seller-target');
            document.querySelectorAll(`.item-checkbox[data-item-seller="${sellerName}"]`).forEach(icb => {
                icb.checked = this.checked;
            });
            calculateTotal();
        });
    });

    // Run once on load to set initial state
    calculateTotal();
    if (checkoutBtn) {
        checkoutBtn.addEventListener('click', function (e) {
            e.preventDefault();
            const selectedIds = [];
            document.querySelectorAll('.item-checkbox:checked').forEach(cb => {
                // Get the ID from the row ID (cart-item-15 -> 15)
                const rowId = cb.closest('.cart-item-row').id.split('-').pop();
                selectedIds.push(rowId);
            });

            if (selectedIds.length > 0) {
                // Redirect to checkout with selected item IDs
                window.location.href = `/checkout/?items=${selectedIds.join(',')}`;
            }
        });
    }
});