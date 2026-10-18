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

    document.querySelectorAll('.cart-item-row').forEach(function (row) {
      const checkbox = row.querySelector('.item-checkbox');
      if (checkbox && checkbox.checked) {
        const price = parseFloat(row.getAttribute('data-price')) || 0;
        const qty = parseInt(row.getAttribute('data-quantity'), 10) || 0;
        total += price * qty;
        count++;
      }
    });

    const formatted =
      '₱' +
      total.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });

    if (grandTotalDisplay) grandTotalDisplay.innerText = formatted;
    if (subtotalDisplay) subtotalDisplay.innerText = formatted;
    if (selectedCountDisplay) {
      selectedCountDisplay.innerText = count + (count === 1 ? ' Item' : ' Items');
    }
    if (checkoutBtn) {
      checkoutBtn.disabled = count === 0;
      checkoutBtn.classList.toggle('disabled', count === 0);
    }

    sellerCheckboxes.forEach(function (scb) {
      const key = scb.getAttribute('data-seller-target');
      const items = document.querySelectorAll(
        '.item-checkbox[data-item-seller="' + key + '"]'
      );
      if (!items.length) return;
      const allOn = Array.prototype.every.call(items, function (i) {
        return i.checked;
      });
      const someOn = Array.prototype.some.call(items, function (i) {
        return i.checked;
      });
      scb.checked = allOn;
      scb.indeterminate = someOn && !allOn;
    });
  }

  itemCheckboxes.forEach(function (cb) {
    cb.addEventListener('change', calculateTotal);
  });

  sellerCheckboxes.forEach(function (scb) {
    scb.addEventListener('change', function () {
      const key = this.getAttribute('data-seller-target');
      document
        .querySelectorAll('.item-checkbox[data-item-seller="' + key + '"]')
        .forEach(function (icb) {
          icb.checked = scb.checked;
        });
      calculateTotal();
    });
  });

  calculateTotal();

  if (checkoutBtn) {
    checkoutBtn.addEventListener('click', function (e) {
      e.preventDefault();
      if (this.disabled || this.classList.contains('disabled')) return;

      const selectedIds = [];
      document.querySelectorAll('.item-checkbox:checked').forEach(function (cb) {
        if (cb.value) {
          selectedIds.push(cb.value);
        } else {
          const row = cb.closest('.cart-item-row');
          if (row && row.id) {
            selectedIds.push(row.id.split('-').pop());
          }
        }
      });

      if (!selectedIds.length) return;

      const base = this.getAttribute('data-checkout-url') || '/checkout/';
      const sep = base.indexOf('?') >= 0 ? '&' : '?';
      window.location.href = base + sep + 'items=' + selectedIds.join(',');
    });
  }
});

/** Confirm before removing a cart item. Returns false to cancel navigation. */
function confirmRemove(event, productName) {
  const name = productName || 'this item';
  if (typeof Swal !== 'undefined') {
    event.preventDefault();
    const href = event.currentTarget.getAttribute('href');
    Swal.fire({
      title: 'Remove from cart?',
      html: '<p class="mb-0">Remove <strong>' + name + '</strong> from your cart?</p>',
      icon: 'warning',
      showCancelButton: true,
      confirmButtonColor: '#dc3545',
      cancelButtonColor: '#6c757d',
      confirmButtonText: 'Yes, remove',
      cancelButtonText: 'Cancel',
    }).then(function (result) {
      if (result.isConfirmed && href) {
        window.location.href = href;
      }
    });
    return false;
  }
  return window.confirm('Remove "' + name + '" from your cart?');
}