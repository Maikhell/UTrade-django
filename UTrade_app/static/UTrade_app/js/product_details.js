// ================= GLOBAL SAFE INIT =================
let variantData = [];
const variantDataElement = document.getElementById("variant-data");
if (variantDataElement) {
  try {
    variantData = JSON.parse(variantDataElement.textContent);
  } catch (e) {
    console.error("Variant JSON parse error:", e);
  }
}

// ================= WISHLIST =================
async function toggleWishlist(
  productId,
  buttonElement,
  isWishlistPage = false,
) {
  if (!buttonElement || typeof buttonElement.querySelector !== "function")
    return;

  const icon = buttonElement.querySelector("i");
  const csrftoken = document.querySelector("[name=csrfmiddlewaretoken]")?.value;

  try {
    const response = await fetch(`/wishlist/toggle/${productId}/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrftoken,
        "X-Requested-With": "XMLHttpRequest",
      },
    });

    const data = await response.json();

    if (data.status === "success") {
      if (data.action === "added") {
        icon.classList.replace("bi-heart", "bi-heart-fill");
        Swal.fire({
          toast: true,
          position: "top-end",
          icon: "success",
          title: "Added to Wishlist",
          showConfirmButton: false,
          timer: 1500,
        });
      } else {
        icon.classList.replace("bi-heart-fill", "bi-heart");

        if (isWishlistPage) {
          const card = document.getElementById(`wishlist-item-${productId}`);
          if (card) {
            card.style.transition = "0.3s";
            card.style.opacity = "0";
            card.style.transform = "scale(0.9)";
            setTimeout(() => card.remove(), 300);
          }
        }

        Swal.fire({
          toast: true,
          position: "top-end",
          icon: "info",
          title: "Removed from Wishlist",
          showConfirmButton: false,
          timer: 1500,
        });
      }
    }
  } catch {
    Swal.fire("Oops!", "Something went wrong. Are you logged in?", "error");
  }
}

// ================= IMAGE + VARIANT DISPLAY =================
function updateProductDisplay(variant) {
  if (!variant) return;

  const priceEl = document.getElementById("displayPrice");
  const detailsDiv = document.getElementById("variantDetails");
  const flawsEl = document.getElementById("variantFlaws");
  const conditionBadge = document.getElementById("variantConditionBadge");
  const nameDisplay = document.getElementById("variantNameDisplay");
  // ADDED: Attribute display element
  const attrDisplay = document.getElementById("variantAttributeDisplay");

  if (priceEl) priceEl.innerText = `₱${parseFloat(variant.price).toFixed(2)}`;
  if (detailsDiv) detailsDiv.classList.remove("d-none");
  if (nameDisplay) nameDisplay.innerText = variant.name;
  if (conditionBadge) conditionBadge.innerText = variant.condition;
  if (flawsEl) flawsEl.innerText = `Notes: ${variant.flaws}`;

  // NEW: Logic to show the separated attribute (XL, Red, etc.)
  if (attrDisplay) {
    if (variant.attribute) {
      attrDisplay.innerText = variant.attribute;
      attrDisplay.classList.remove("d-none");
    } else {
      attrDisplay.classList.add("d-none");
    }
  }

  const img = document.getElementById("mainDisplayImage");
  if (img && variant.image_url) img.src = variant.image_url;
}

function changeImage(url, element = null) {
  const mainImg = document.getElementById("mainDisplayImage");
  if (mainImg) {
    mainImg.style.opacity = "0";
    setTimeout(() => {
      mainImg.src = url;
      mainImg.style.opacity = "1";
    }, 200);
  }

  document.querySelectorAll(".thumbnail-wrapper").forEach((el) => {
    el.classList.remove("border-success", "border-2");
  });

  if (element) {
    element.classList.add("border-success", "border-2");
  }

  const matchedVariant = variantData.find((v) => v.image_url.includes(url));
  if (matchedVariant) {
    updateProductDisplay(matchedVariant);
  }
}

// ================= VARIANT CHANGE =================
function onVariantChange(variantId) {
  const selectedVariant = variantData.find((v) => v.id == variantId);
  if (selectedVariant) {
    changeImage(selectedVariant.image_url);
    updateProductDisplay(selectedVariant);
  }
}

// ================= VARIANT SELECTOR =================
function openVariantSelector(productId, productName, isPreOrder = false) {
  if (!variantData || variantData.length === 0) {
    isPreOrder
      ? performPreOrderRequest([{ variant_id: productId, quantity: 1 }])
      : performAddToCart([{ variant_id: productId, quantity: 1 }]);
    return;
  }

  let optionsHtml = `<option value="">Choose a variant / size…</option>`;
  let chipsHtml = "";

  variantData.forEach((v) => {
    const isOut = v.stock <= 0;
    const label =
      [v.name, v.attribute].filter(Boolean).join(" · ") || `Variant #${v.id}`;
    const sizeLabel = v.attribute || v.name || label;
    const imgUrl = (v.image_url || "").trim();

    optionsHtml += `
      <option value="${v.id}"
              data-price="${v.price}"
              data-stock="${v.stock}"
              data-condition="${(v.condition || "").replace(/"/g, "&quot;")}"
              data-name="${(v.name || "").replace(/"/g, "&quot;")}"
              data-attr="${(v.attribute || "").replace(/"/g, "&quot;")}"
              data-image="${imgUrl.replace(/"/g, "&quot;")}"
              ${isOut ? "disabled" : ""}>
        ${label} — ₱${parseFloat(v.price).toFixed(2)}${isOut ? " (Sold out)" : ` · ${v.stock} left`}
      </option>`;

    chipsHtml += `
      <button type="button"
              class="btn btn-sm rounded-pill variant-chip ${isOut ? "btn-outline-secondary opacity-50" : "btn-outline-dark"}"
              data-id="${v.id}"
              ${isOut ? "disabled" : ""}
              style="min-width: 3rem; font-weight: 600;">
        ${sizeLabel}
      </button>`;
  });

  const html = `
  <div class="text-start">
    <div class="d-flex justify-content-center mb-3">
      <div id="swalVariantImgWrap"
           class="rounded-3 border bg-light d-flex align-items-center justify-content-center overflow-hidden"
           style="width:120px;height:120px;">
        <img id="swalVariantImg" src="" alt=""
             class="w-100 h-100 d-none" style="object-fit:cover;" />
        <i id="swalVariantImgPlaceholder" class="bi bi-image text-muted fs-2"></i>
      </div>
    </div>
    <div class="text-start">
      <label class="form-label small fw-bold text-secondary mb-1">Variants / sizes</label>
      <select id="swalVariantSelect" class="form-select form-select-lg mb-3">
        ${optionsHtml}
      </select>

      <div class="small text-muted mb-1">Quick select size</div>
      <div id="swalVariantChips" class="d-flex flex-wrap gap-2 mb-3">
        ${chipsHtml}
      </div>

      <div id="swalVariantInfo" class="p-3 bg-light rounded-3 small mb-3 d-none">
        <div class="d-flex justify-content-between">
          <span class="text-muted">Price</span>
          <strong id="swalModalPrice" class="text-success"></strong>
        </div>
        <div class="d-flex justify-content-between">
          <span class="text-muted">Stock</span>
          <span id="swalModalStock"></span>
        </div>
        <div class="d-flex justify-content-between">
          <span class="text-muted">Condition</span>
          <span id="swalModalCondition"></span>
        </div>
      </div>

      <label class="form-label small fw-bold text-secondary">Quantity</label>
      <div class="input-group" style="max-width: 160px;">
        <button type="button" class="btn btn-outline-secondary" id="swalQtyMinus">−</button>
        <input type="number" id="swalVariantQty" class="form-control text-center" value="1" min="1" />
        <button type="button" class="btn btn-outline-secondary" id="swalQtyPlus">+</button>
      </div>
    </div>
  `;

  Swal.fire({
    title: isPreOrder
      ? `Pre-order ${productName}`
      : `Add to Cart — ${productName}`,
    html,
    showCancelButton: true,
    confirmButtonText: isPreOrder ? "Confirm Pre-order" : "Add to Cart",
    confirmButtonColor: isPreOrder ? "#0d6efd" : "#198754",
    focusConfirm: false,
    didOpen: () => {
      const select = document.getElementById("swalVariantSelect");
      const chips = document.getElementById("swalVariantChips");
      const info = document.getElementById("swalVariantInfo");
      const qtyInput = document.getElementById("swalVariantQty");

      function highlightChip(id) {
        chips.querySelectorAll(".variant-chip").forEach((btn) => {
          const on = btn.dataset.id === String(id);
          btn.classList.toggle("btn-success", on);
          btn.classList.toggle("text-white", on);
          btn.classList.toggle("btn-outline-dark", !on && !btn.disabled);
        });
      }
      function setVariantPreview(url) {
        const img = document.getElementById("swalVariantImg");
        const placeholder = document.getElementById(
          "swalVariantImgPlaceholder",
        );
        if (!img || !placeholder) return;

        if (url) {
          img.onload = () => {
            img.classList.remove("d-none");
            placeholder.classList.add("d-none");
          };
          img.onerror = () => {
            img.classList.add("d-none");
            placeholder.classList.remove("d-none");
            img.removeAttribute("src");
          };
          img.src = url;
        } else {
          img.classList.add("d-none");
          img.removeAttribute("src");
          placeholder.classList.remove("d-none");
        }
      }
      function syncFromSelect() {
        const opt = select.selectedOptions[0];
        if (!opt || !opt.value) {
          info.classList.add("d-none");
          highlightChip(null);
          setVariantPreview(""); // show placeholder
          return;
        }

        document.getElementById("swalModalPrice").textContent =
          "₱" + parseFloat(opt.dataset.price || 0).toFixed(2);
        document.getElementById("swalModalStock").textContent =
          opt.dataset.stock || "—";
        document.getElementById("swalModalCondition").textContent =
          opt.dataset.condition || "—";
        info.classList.remove("d-none");
        highlightChip(opt.value);

        setVariantPreview((opt.dataset.image || "").trim());

        const max = parseInt(opt.dataset.stock, 10) || 1;
        qtyInput.max = max;
        if (parseInt(qtyInput.value, 10) > max) qtyInput.value = max;

        onVariantChange(opt.value);
      }

      select.addEventListener("change", syncFromSelect);

      chips.querySelectorAll(".variant-chip:not([disabled])").forEach((btn) => {
        btn.addEventListener("click", () => {
          select.value = btn.dataset.id;
          select.dispatchEvent(new Event("change"));
        });
      });

      document.getElementById("swalQtyMinus").onclick = () => {
        let v = parseInt(qtyInput.value, 10) || 1;
        qtyInput.value = Math.max(1, v - 1);
      };
      document.getElementById("swalQtyPlus").onclick = () => {
        let v = parseInt(qtyInput.value, 10) || 1;
        const max = parseInt(qtyInput.max, 10) || 99;
        qtyInput.value = Math.min(max, v + 1);
      };
    },
    preConfirm: () => {
      const select = document.getElementById("swalVariantSelect");
      const qtyInput = document.getElementById("swalVariantQty");
      if (!select || !select.value) {
        Swal.showValidationMessage("Please select a variant / size.");
        return false;
      }
      const qty = parseInt(qtyInput.value, 10) || 1;
      const max = parseInt(select.selectedOptions[0]?.dataset.stock, 10) || 1;
      if (qty < 1 || qty > max) {
        Swal.showValidationMessage(`Quantity must be between 1 and ${max}.`);
        return false;
      }
      return [{ variant_id: select.value, quantity: qty }];
    },
  }).then((result) => {
    if (result.isConfirmed && result.value) {
      isPreOrder
        ? performPreOrderRequest(result.value)
        : performAddToCart(result.value);
    }
  });
}
function toggleQtyInput(varId) {
  const cb = document.getElementById(`check_var_${varId}`);
  const qtyInput = document.getElementById(`qty_var_${varId}`);
  const minusBtn = document.getElementById(`minus_btn_${varId}`);
  const plusBtn = document.getElementById(`plus_btn_${varId}`);

  const isEnabled = cb.checked;
  if (qtyInput) qtyInput.disabled = !isEnabled;
  if (minusBtn) minusBtn.disabled = !isEnabled;
  if (plusBtn) plusBtn.disabled = !isEnabled;

  // Optional: Auto update preview on main image
  if (isEnabled) {
    onVariantChange(varId);
  }
}

function adjustQty(varId, delta) {
  const input = document.getElementById(`qty_var_${varId}`);
  if (!input || input.disabled) return;

  let currentVal = parseInt(input.value) || 1;
  const maxStock = parseInt(input.getAttribute("data-max-stock")) || 99;

  currentVal += delta;
  if (currentVal < 1) currentVal = 1;
  if (currentVal > maxStock) currentVal = maxStock;

  input.value = currentVal;
}
// ================= PREORDER =================
function performAddToCart(items) {
  const csrftoken = document.querySelector("[name=csrfmiddlewaretoken]")?.value;

  fetch(`/cart/add-batch/`, {
    method: "POST",
    headers: {
      "X-CSRFToken": csrftoken,
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify({ items: items }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        const badge = document.getElementById("cart-count");
        if (badge) {
          badge.innerText = data.cart_count;
          badge.style.display = "inline-block";
        }
        Swal.fire({
          icon: "success",
          title: "Added to Cart!",
          timer: 1500,
          showConfirmButton: false,
        });
      } else {
        Swal.fire({ icon: "error", title: "Error", text: data.message });
      }
    })
    .catch(() =>
      Swal.fire("Error", "Login required or network failure.", "error"),
    );
}

// ================= BATCH PREORDER =================
function performPreOrderRequest(items) {
  const csrftoken = document.querySelector("[name=csrfmiddlewaretoken]")?.value;

  fetch(`/preorder/request-batch/`, {
    method: "POST",
    headers: {
      "X-CSRFToken": csrftoken,
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify({ items: items, status: "Pending" }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        Swal.fire({
          icon: "success",
          title: "Pre-order Sent!",
          text: "Pending seller approval.",
        });
      } else {
        Swal.fire({ icon: "error", title: "Error", text: data.message });
      }
    })
    .catch(() => Swal.fire("Connection Error", "Try again later", "error"));
}
// ================= SIMPLE ADD TO CART =================
function addToCart(productId, buttonElement) {
  const csrftoken = document.querySelector("[name=csrfmiddlewaretoken]")?.value;

  fetch(`/cart/add/${productId}/`, {
    method: "POST",
    headers: {
      "X-CSRFToken": csrftoken,
      "X-Requested-With": "XMLHttpRequest",
    },
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        const badge = document.getElementById("cart-count");
        if (badge) {
          badge.innerText = data.cart_count;
          badge.style.display = "inline-block";
        }
        Swal.fire({
          toast: true,
          position: "top-end",
          icon: "success",
          title: "Added to Cart",
          timer: 1500,
          showConfirmButton: false,
        });
      } else {
        Swal.fire({ icon: "error", title: "Error", text: data.message });
      }
    })
    .catch(() => Swal.fire("Login Required", "", "warning"));
}

// ================= HELPERS =================
function addToCartWithVariant(productId) {
  const name = document.querySelector("h1")?.innerText || "Product";
  openVariantSelector(productId, name);
}

function showLoginPrompt() {
  const loginUrl = document.getElementById("login-url").value;
  Swal.fire({
    title: "Login Required",
    text: "You need to log in first.",
    icon: "info",
    showCancelButton: true,
    confirmButtonText: "Login",
  }).then((r) => {
    if (r.isConfirmed) window.location.href = loginUrl;
  });
}

function showVerificationModal() {
  const statusEl = document.getElementById("user-verification-status");
  if (!statusEl) return;

  const status = statusEl.value;
  if (status === "unverified" || status === "Pending") {
    const modalEl = document.getElementById("verificationModal");
    if (modalEl) {
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    }
  }
}
