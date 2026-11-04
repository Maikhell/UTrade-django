document.addEventListener('DOMContentLoaded', function () {
  // Guard against double-loading.
  if (window.__utradeCartInit) return;
  window.__utradeCartInit = true;

  const itemCheckboxes = document.querySelectorAll('.item-checkbox');
  const sellerCheckboxes = document.querySelectorAll('.seller-checkbox');
  const grandTotalDisplay = document.getElementById('grand-total-display');
  const subtotalDisplay = document.getElementById('subtotal-display');
  const selectedCountDisplay = document.getElementById('selected-count');
  const checkoutBtn = document.getElementById('checkout-btn');
  const summaryList = document.getElementById('summary-items');
  const summaryEmpty = document.getElementById('summary-empty');

  function money(n) {
    return '₱' + n.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function selectedItems() {
    const out = [];
    document.querySelectorAll('.cart-item-row').forEach(function (row) {
      const cb = row.querySelector('.item-checkbox');
      if (!cb || !cb.checked) return;
      out.push({
        id: cb.value || (row.id || '').split('-').pop(),
        name: row.getAttribute('data-name') || 'Item',
        variant: row.getAttribute('data-variant') || '',
        price: parseFloat(row.getAttribute('data-price')) || 0,
        qty: parseInt(row.getAttribute('data-quantity'), 10) || 0,
        seller: cb.getAttribute('data-item-seller'),
      });
    });
    return out;
  }

  function renderSummary(items) {
    if (!summaryList) return;
    summaryList.innerHTML = '';
    if (summaryEmpty) summaryEmpty.style.display = items.length ? 'none' : '';
    items.forEach(function (it) {
      const li = document.createElement('li');
      li.className = 'ct-sum-item';

      const left = document.createElement('div');
      const name = document.createElement('span');
      name.className = 'ct-sum-name';
      name.textContent = it.name;
      const sub = document.createElement('span');
      sub.className = 'ct-sum-sub';
      sub.textContent = (it.variant ? it.variant + ' · ' : '') + it.qty + ' × ' + money(it.price);
      left.appendChild(name);
      left.appendChild(sub);

      const amt = document.createElement('span');
      amt.className = 'ct-sum-amt';
      amt.textContent = money(it.price * it.qty);

      li.appendChild(left);
      li.appendChild(amt);
      summaryList.appendChild(li);
    });
  }

  function calculateTotal() {
    const items = selectedItems();
    const total = items.reduce(function (s, it) { return s + it.price * it.qty; }, 0);

    if (grandTotalDisplay) grandTotalDisplay.innerText = money(total);
    if (subtotalDisplay) subtotalDisplay.innerText = money(total);
    if (selectedCountDisplay) {
      selectedCountDisplay.innerText = items.length + (items.length === 1 ? ' Item' : ' Items');
    }
    if (checkoutBtn) {
      checkoutBtn.disabled = items.length === 0;
      checkoutBtn.classList.toggle('disabled', items.length === 0);
    }
    renderSummary(items);

    sellerCheckboxes.forEach(function (scb) {
      const key = scb.getAttribute('data-seller-target');
      const boxes = document.querySelectorAll('.item-checkbox[data-item-seller="' + key + '"]');
      if (!boxes.length) return;
      const allOn = Array.prototype.every.call(boxes, function (i) { return i.checked; });
      const someOn = Array.prototype.some.call(boxes, function (i) { return i.checked; });
      scb.checked = allOn;
      scb.indeterminate = someOn && !allOn;
    });
  }

  itemCheckboxes.forEach(function (cb) { cb.addEventListener('change', calculateTotal); });

  sellerCheckboxes.forEach(function (scb) {
    scb.addEventListener('change', function () {
      const key = this.getAttribute('data-seller-target');
      document.querySelectorAll('.item-checkbox[data-item-seller="' + key + '"]')
        .forEach(function (icb) { icb.checked = scb.checked; });
      calculateTotal();
    });
  });

  calculateTotal();

  // ---- Confirm, then go to checkout ----
  function goToCheckout(ids) {
    const base = checkoutBtn.getAttribute('data-checkout-url') || '/checkout/';
    window.location.href = base + (base.indexOf('?') === -1 ? '?' : '&') +
      'items=' + encodeURIComponent(ids.join(','));
  }

  if (checkoutBtn) {
    checkoutBtn.addEventListener('click', function (e) {
      e.preventDefault();
      if (this.disabled || this.classList.contains('disabled')) return;

      const items = selectedItems();
      if (!items.length) return;

      const ids = items.map(function (i) { return i.id; });
      const total = items.reduce(function (s, it) { return s + it.price * it.qty; }, 0);
      const sellers = new Set(items.map(function (i) { return i.seller; })).size;
      const qty = items.reduce(function (s, it) { return s + it.qty; }, 0);

      if (window.Swal) {
        // Built from numbers only (no user text), so it is safe as HTML.
        Swal.fire({
          icon: 'question',
          title: 'Proceed to checkout?',
          html:
            '<p class="mb-1">You are checking out <strong>' + items.length +
            (items.length === 1 ? ' item' : ' items') + '</strong> (' + qty + ' pcs) from <strong>' +
            sellers + (sellers === 1 ? ' seller' : ' sellers') + '</strong>.</p>' +
            '<p class="mb-2">Subtotal: <strong>' + money(total) + '</strong></p>' +
            (sellers > 1
              ? '<p class="small text-muted mb-0">Each seller will receive a separate order.</p>'
              : ''),
          showCancelButton: true,
          confirmButtonText: 'Yes, continue',
          cancelButtonText: 'Review cart',
          confirmButtonColor: '#198754',
          cancelButtonColor: '#6c757d',
        }).then(function (r) { if (r.isConfirmed) goToCheckout(ids); });
      } else if (window.confirm('Proceed to checkout with ' + items.length + ' item(s), subtotal ' + money(total) + '?')) {
        goToCheckout(ids);
      }
    });
  }
});

/** Confirm before removing a cart item. Returns false to cancel navigation. */
function confirmRemove(event, productName) {
  const name = productName || 'this item';
  if (typeof Swal !== 'undefined') {
    event.preventDefault();
    const href = event.currentTarget.getAttribute('href');

    // Built with DOM nodes so the product name can never inject HTML.
    const p = document.createElement('p');
    p.className = 'mb-0';
    p.appendChild(document.createTextNode('Remove '));
    const strong = document.createElement('strong');
    strong.textContent = name;
    p.appendChild(strong);
    p.appendChild(document.createTextNode(' from your cart?'));

    Swal.fire({
      title: 'Remove from cart?',
      html: p,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonColor: '#dc3545',
      cancelButtonColor: '#6c757d',
      confirmButtonText: 'Yes, remove',
      cancelButtonText: 'Cancel',
    }).then(function (result) {
      if (result.isConfirmed && href) window.location.href = href;
    });
    return false;
  }
  return window.confirm('Remove "' + name + '" from your cart?');
}
