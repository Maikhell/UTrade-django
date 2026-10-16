if (typeof window.itemCount === "undefined") {
  window.itemCount = 0;
  window.selectedFiles = [];
  window.allStagedProducts = [];
  window.productVariants = [];
  window.currentSelectedImageIndex = null;
  window.PROHIBITED_WORDS = [];
  window.existingImageUrls = [];          // for edit restore
  window.editingStagedId = null;
}

async function loadProhibitedWords() {
  try {
    const response = await fetch("/api/prohibited-words/");
    const data = await response.json();
    window.PROHIBITED_WORDS = data.prohibited_words || [];
  } catch (error) {
    console.error("Failed to load prohibited words:", error);
    window.PROHIBITED_WORDS = ["scam", "drugs", "shabu"];
  }
}
loadProhibitedWords();

/* ===================== IMAGE PREVIEW ===================== */
function previewMultipleImages(event) {
  const container = document.getElementById("image_preview_container");
  if (!container) return;

  // Keep any previously restored existing images (edit mode)
  const existingWrappers = Array.from(
    container.querySelectorAll(".preview-wrapper[data-existing='1']")
  );

  container.innerHTML = "";
  existingWrappers.forEach((w) => container.appendChild(w));

  const newFiles = Array.from(event.target.files || []);
  window.selectedFiles = newFiles;          // only the NEW files for upload

  newFiles.forEach((file, index) => {
    const reader = new FileReader();
    reader.onload = function (e) {
      const wrapper = document.createElement("div");
      wrapper.className = "preview-wrapper animate__animated animate__fadeIn";
      const isMain = existingWrappers.length === 0 && index === 0;
      const badge = isMain ? '<span class="main-badge">COVER</span>' : "";
      wrapper.innerHTML = `
        ${badge}
        <img src="${e.target.result}" class="preview-box ${isMain ? "is-main-image" : ""}">
      `;
      container.appendChild(wrapper);
    };
    reader.readAsDataURL(file);
  });
}

/* ===================== ATTRIBUTE TAGS ===================== */
function addTag(type) {
  const input = document.getElementById(`${type}_input`);
  const tagContainer = document.getElementById(`${type}_tags`);
  const mainDisplay = document.getElementById("attribute_pills");
  if (!input || !tagContainer || !mainDisplay) return;

  const val = input.value.trim();
  if (!val) return;

  if (!window.currentAttributes)
    window.currentAttributes = { colors: [], sizes: [] };
  if (!window.currentAttributes[`${type}s`])
    window.currentAttributes[`${type}s`] = [];

  if (!window.currentAttributes[`${type}s`].includes(val)) {
    window.currentAttributes[`${type}s`].push(val);
    const pillHtml = `
      <span class="badge rounded-pill bg-light text-dark border p-2 me-1 mb-1">
        ${val}
        <i class="bi bi-x-circle-fill ms-1 text-danger cursor-pointer"
           onclick="removeTag('${type}', '${val}', this)"></i>
      </span>`;
    mainDisplay.insertAdjacentHTML("beforeend", pillHtml);
    tagContainer.insertAdjacentHTML("beforeend", pillHtml);
  }
  input.value = "";
}

function removeTag(type, value, element) {
  if (!window.currentAttributes) return;
  window.currentAttributes[`${type}s`] = (
    window.currentAttributes[`${type}s`] || []
  ).filter((val) => val !== value);
  if (element && element.parentElement) element.parentElement.remove();

  const mainPills = document.getElementById("attribute_pills");
  if (!mainPills) return;
  mainPills.querySelectorAll(".badge").forEach((pill) => {
    if (pill.innerText.trim().includes(value)) pill.remove();
  });
}

function toggleCustomCondition(select) {
  const customInput = document.getElementById("custom_condition_input");
  if (!customInput) return;
  if (select.value === "Other") {
    customInput.classList.remove("d-none");
    customInput.focus();
  } else {
    customInput.classList.add("d-none");
  }
}

/* ===================== MEETUP DAYS + TIME RANGE ===================== */
function getSelectedMeetupDays() {
  return Array.from(document.querySelectorAll(".meetup-day:checked")).map(
    (cb) => cb.value,
  );
}

function timeToMinutes(timeStr) {
  if (!timeStr || typeof timeStr !== "string") return null;
  const parts = timeStr.trim().split(":");
  if (parts.length < 2) return null;
  const h = parseInt(parts[0], 10);
  const m = parseInt(parts[1], 10);
  if (Number.isNaN(h) || Number.isNaN(m)) return null;
  if (h < 0 || h > 23 || m < 0 || m > 59) return null;
  return h * 60 + m;
}

function setFieldError(inputEl, errorId, message) {
  const errorEl = document.getElementById(errorId);
  if (inputEl) inputEl.classList.add("is-invalid");
  if (errorEl) {
    errorEl.textContent = message || "";
    errorEl.classList.remove("d-none");
    errorEl.style.display = "block";
  }
}

function clearFieldError(inputEl, errorId) {
  const errorEl = document.getElementById(errorId);
  if (inputEl) inputEl.classList.remove("is-invalid");
  if (errorEl) {
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
    errorEl.style.display = "none";
  }
}

function validateMeetupDays(showErrors = true) {
  const days = getSelectedMeetupDays();
  const errorEl = document.getElementById("days_error");
  if (days.length === 0) {
    if (showErrors && errorEl) {
      errorEl.textContent = "Please select at least one day (Mon–Sat).";
      errorEl.classList.remove("d-none");
      errorEl.style.display = "block";
    }
    return false;
  }
  if (errorEl) {
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
    errorEl.style.display = "none";
  }
  return true;
}

function validateMeetupTimeRange(showErrors = true) {
  const fromInput = document.getElementById("meetup_time_from");
  const toInput = document.getElementById("meetup_time_to");
  if (!fromInput || !toInput) {
    if (showErrors) {
      Swal.fire("Form Error", "Time inputs are missing in the page HTML.", "error");
    }
    return false;
  }

  const fromVal = (fromInput.value || "").trim();
  const toVal = (toInput.value || "").trim();

  clearFieldError(fromInput, "from_time_error");
  clearFieldError(toInput, "to_time_error");
  const rangeError = document.getElementById("time_range_error");
  if (rangeError) {
    rangeError.textContent = "";
    rangeError.classList.add("d-none");
    rangeError.style.display = "none";
  }

  let valid = true;
  const minAllowed = 7 * 60;
  const maxAllowed = 21 * 60;

  if (!fromVal) {
    if (showErrors) setFieldError(fromInput, "from_time_error", "From time is required.");
    valid = false;
  }
  if (!toVal) {
    if (showErrors) setFieldError(toInput, "to_time_error", "To time is required.");
    valid = false;
  }
  if (!valid) return false;

  const fromMins = timeToMinutes(fromVal);
  const toMins = timeToMinutes(toVal);

  if (fromMins === null) {
    if (showErrors) setFieldError(fromInput, "from_time_error", "Invalid From time.");
    return false;
  }
  if (toMins === null) {
    if (showErrors) setFieldError(toInput, "to_time_error", "Invalid To time.");
    return false;
  }

  if (fromMins < minAllowed || fromMins > maxAllowed) {
    if (showErrors) {
      setFieldError(fromInput, "from_time_error", "Must be between 7:00 AM and 9:00 PM.");
    }
    valid = false;
  }
  if (toMins < minAllowed || toMins > maxAllowed) {
    if (showErrors) {
      setFieldError(toInput, "to_time_error", "Must be between 7:00 AM and 9:00 PM.");
    }
    valid = false;
  }

  if (valid && fromMins >= toMins) {
    if (showErrors) {
      setFieldError(fromInput, "from_time_error", "Must be earlier than To.");
      setFieldError(toInput, "to_time_error", "Must be later than From.");
      if (rangeError) {
        rangeError.textContent = "From time must be earlier than To time.";
        rangeError.classList.remove("d-none");
        rangeError.style.display = "block";
      }
    }
    valid = false;
  }
  return valid;
}

/* ===================== PRODUCT CODE HELPERS ===================== */
function getProductCodeValue() {
  const el = document.getElementById("product_code");
  return el ? (el.value || "").trim() : "";
}

function setProductCodeValue(code) {
  const el = document.getElementById("product_code");
  if (el && code) el.value = code;
  const hidden = document.getElementById("product_code_hidden");
  if (hidden && code) hidden.value = code;
}

async function refreshNextProductCode() {
  try {
    const response = await fetch("/api/next-product-code/");
    const data = await response.json();
    if (data.product_code) setProductCodeValue(data.product_code);
  } catch (e) {
    console.warn("Could not refresh product code:", e);
  }
}

/* ===================== ADD TO STAGING ===================== */
async function addToStaging() {
  const nameEl = document.getElementById("name");
  const priceEl = document.getElementById("price");
  const stocksEl = document.getElementById("stocks");
  const descEl = document.getElementById("description");
  const categoryEl = document.getElementById("category");
  const preOrderElement = document.getElementById("is_pre_order");
  const locationInput = document.getElementById("location_input");
  const fromInput = document.getElementById("meetup_time_from");
  const toInput = document.getElementById("meetup_time_to");
  const ownerTypeEl = document.getElementById("owner_type");
  const attributesSection = document.getElementById("attributes_section");

  const isVariantMode =
    attributesSection && !attributesSection.classList.contains("d-none");
  const isPreOrder = !!(preOrderElement && preOrderElement.checked);

  [nameEl, priceEl, stocksEl, locationInput, fromInput, toInput].forEach(
    (el) => el && el.classList.remove("is-invalid"),
  );

  // Approval letter (officers only)
  if (typeof validateApprovalLetter === "function" && !validateApprovalLetter()) {
    return Swal.fire(
      "Letter of Approval Required",
      "Please attach a Letter of Approval (JPG/PNG, max 10 MB).",
      "warning",
    );
  }

  if (!locationInput || !locationInput.value.trim()) {
    if (locationInput) locationInput.classList.add("is-invalid");
    return Swal.fire("Location Required", "Please enter a campus meetup spot.", "warning");
  }

  if (typeof validateMeetupDays === "function") {
    if (!validateMeetupDays(true)) {
      return Swal.fire(
        "Days Required",
        "Please select at least one available day (Mon–Sat).",
        "warning",
      );
    }
  } else if (!getSelectedMeetupDays().length) {
    return Swal.fire(
      "Days Required",
      "Please select at least one available day (Mon–Sat).",
      "warning",
    );
  }

  const selectedDays = getSelectedMeetupDays();

  if (!fromInput || !toInput) {
    return Swal.fire(
      "Form Error",
      "Time inputs are missing. Expected #meetup_time_from and #meetup_time_to.",
      "error",
    );
  }

  if (!(fromInput.value || "").trim() || !(toInput.value || "").trim()) {
    if (!(fromInput.value || "").trim()) fromInput.classList.add("is-invalid");
    if (!(toInput.value || "").trim()) toInput.classList.add("is-invalid");
    return Swal.fire("Time Required", "Please set both From and To meetup times.", "warning");
  }

  const timeValid =
    typeof validateMeetupTimeRange === "function"
      ? validateMeetupTimeRange(true)
      : true;
  if (!timeValid) {
    return Swal.fire(
      "Invalid Time Range",
      "Time must be between 7:00 AM and 9:00 PM, and From must be earlier than To.",
      "error",
    );
  }

  if (!nameEl || !nameEl.value.trim()) {
    if (nameEl) nameEl.classList.add("is-invalid");
    return Swal.fire("Required Fields", "Product name is required.", "error");
  }

  if (validateProhibitedInput(nameEl) || validateProhibitedInput(descEl)) {
    return Swal.fire(
      "Prohibited Content",
      "Please remove restricted words before proceeding.",
      "error",
    );
  }

  let finalPrice, finalStocks;
  if (isVariantMode) {
    if (!window.productVariants || window.productVariants.length === 0) {
      return Swal.fire("Variations Required", "Please add at least one variety.", "warning");
    }
    finalPrice = window.productVariants[0].price;
    finalStocks = window.productVariants.reduce((sum, v) => sum + (v.stock || 0), 0);
  } else {
    finalPrice = priceEl?.value || 0;
    finalStocks = stocksEl?.value || 0;
  }

  // At least one image (new or existing)
  const hasExistingImages =
    document.querySelectorAll("#image_preview_container .preview-wrapper[data-existing='1']").length > 0;
  if ((!window.selectedFiles || window.selectedFiles.length === 0) && !hasExistingImages) {
    return Swal.fire("Photos Required", "Please select at least one photo.", "warning");
  }

  const categoryId = categoryEl ? categoryEl.value : "";
  if (!categoryId || categoryId === "other") {
    return Swal.fire("Category Required", "Please choose a valid category.", "warning");
  }
  let categoryName = "Uncategorized";
  if (categoryEl && categoryEl.selectedIndex >= 0) {
    categoryName = categoryEl.options[categoryEl.selectedIndex].text;
  }

  const productCode = getProductCodeValue();
  const formData = new FormData();
  formData.append("name", nameEl.value.trim());
  formData.append("description", descEl?.value.trim() || "");
  formData.append("category", categoryId);
  formData.append("product_code", productCode);
  formData.append("location_options", locationInput.value.trim());
  formData.append("available_days", selectedDays.join(","));
  formData.append("meetup_time_from", fromInput.value);
  formData.append("meetup_time_to", toInput.value);
  formData.append("owner_type", ownerTypeEl?.value || "PERSONAL");
  formData.append("pre_order", isPreOrder ? "True" : "False");

  const paymentEl = document.querySelector('input[name="payment"]:checked');
  formData.append("payment", paymentEl ? paymentEl.value : "COP");
  formData.append("variants", JSON.stringify(window.productVariants || []));

  // Existing image IDs to keep (edit mode)
  if (window.existingImageUrls && window.existingImageUrls.length) {
    formData.append("keep_image_ids", JSON.stringify(
      window.existingImageUrls.map((i) => i.id).filter(Boolean)
    ));
  }

  // Approval letter
  const approvalInput = document.getElementById("approval_letter");
  if (approvalInput && approvalInput.files && approvalInput.files[0]) {
    formData.append("approval_letter", approvalInput.files[0]);
  }

  // New gallery images
  window.selectedFiles.forEach((file) => {
    formData.append("images", file);
  });

  Swal.fire({
    title: "Saving to Staging...",
    allowOutsideClick: false,
    didOpen: () => Swal.showLoading(),
  });

  try {
    const response = await fetch("/api/staged-product/add/", {
      method: "POST",
      headers: {
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
      },
      body: formData,
    });

    const result = await response.json();
    if (result.status !== "success") {
      throw new Error(result.message || "Server error.");
    }

    const dbId = result.staged_id;
    const savedCode = result.product_code || productCode;

    // Build card image
    const firstImg = document.querySelector("#image_preview_container img");
    const imageHtml = firstImg
      ? `<img src="${firstImg.src}" class="rounded shadow-sm me-3" style="width:70px;height:70px;object-fit:cover;border:1px solid #dee2e6;">`
      : `<div class="bg-light rounded me-3 d-flex align-items-center justify-content-center" style="width:70px;height:70px;border:1px solid #dee2e6;"><i class="bi bi-image text-muted"></i></div>`;

    const daysLabel = selectedDays.join(", ");
    const timeLabel = `${fromInput.value} – ${toInput.value}`;

    const itemCard = `
      <div class="card staged-item mb-3 p-3 bg-white border-0 shadow-sm animate__animated animate__fadeInRight" data-id="${dbId}">
        <div class="d-flex align-items-start mb-2">
          ${imageHtml}
          <div class="flex-grow-1">
            <div class="d-flex justify-content-between">
              <h6 class="mb-0 fw-bold text-dark">${nameEl.value}</h6>
              <div class="d-flex flex-column gap-2">
                <button class="btn btn-sm text-danger p-0" onclick="removeItem(this, ${dbId})">
                  <i class="bi bi-trash-fill"></i>
                </button>
                <button class="btn btn-sm text-primary p-0" onclick="editItem(${dbId})">
                  <i class="bi bi-pencil-square"></i>
                </button>
              </div>
            </div>
            <div class="mt-1">
              <span class="badge bg-success-subtle text-success small">₱${finalPrice}</span>
              <span class="text-muted small ms-1">Stock: ${finalStocks}</span>
              ${isPreOrder ? `<span class="badge bg-primary-subtle text-primary small ms-1">Pre-order</span>` : ""}
            </div>
          </div>
        </div>
        <div class="small text-muted mb-2 text-truncate-2" style="font-size:0.85rem;">${descEl?.value || ""}</div>
        <div class="d-flex flex-wrap gap-1 mb-2">
          ${savedCode ? `<span class="badge bg-dark text-white fw-normal"><i class="bi bi-upc me-1"></i>${savedCode}</span>` : ""}
          <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-tag me-1"></i>${categoryName}</span>
          <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-geo-alt me-1"></i>${locationInput.value.trim()}</span>
          <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-calendar-week me-1"></i>${daysLabel}</span>
          <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-clock me-1"></i>${timeLabel}</span>
        </div>
      </div>`;

    const stagingArea = document.getElementById("staging_area");
    if (stagingArea) {
      if (stagingArea.querySelector(".empty-msg")) stagingArea.innerHTML = "";
      stagingArea.insertAdjacentHTML("afterbegin", itemCard);
    }

    const countEl = document.getElementById("item_count");
    if (countEl) countEl.innerText = document.querySelectorAll(".staged-item").length;

    // Reset form
    const codeBeforeReset = result.next_product_code || null;
    document.getElementById("product_form")?.reset();
    window.selectedFiles = [];
    window.productVariants = [];
    window.currentSelectedImageIndex = null;
    window.existingImageUrls = [];
    window.editingStagedId = null;

    document.querySelectorAll(".meetup-day").forEach((cb) => (cb.checked = false));

    if (codeBeforeReset) {
      setProductCodeValue(codeBeforeReset);
    } else {
      await refreshNextProductCode();
    }

    const previewContainer = document.getElementById("image_preview_container");
    if (previewContainer) {
      previewContainer.innerHTML = `
        <div class="text-center py-5 text-muted small w-100">Item added successfully.</div>`;
    }

    const variantList = document.getElementById("variant_list");
    if (variantList) variantList.innerHTML = "";

    if (categoryEl) {
      categoryEl.value = "";
      if (typeof handleCategoryChange === "function") handleCategoryChange(categoryEl);
    }

    // Clear approval preview if a new file was chosen
    const approvalPreview = document.getElementById("approval_preview");
    if (approvalPreview) approvalPreview.innerHTML = "";

    Swal.fire({
      toast: true,
      position: "top-end",
      icon: "success",
      title: "Saved to Staging List",
      showConfirmButton: false,
      timer: 2000,
    });
  } catch (error) {
    console.error("Staging Error:", error);
    Swal.fire("Error", error.message || "Failed to connect to server.", "error");
  }
}

/* ===================== EDIT STAGED ITEM ===================== */
async function editItem(stagedId) {
  try {
    const response = await fetch(`/api/staged-product/${stagedId}/`);
    const data = await response.json();
    if (data.error) throw new Error(data.error);

    window.editingStagedId = stagedId;

    const nameEl = document.getElementById("name");
    const descEl = document.getElementById("description");
    if (nameEl) nameEl.value = data.name || "";
    if (descEl) descEl.value = data.description || "";

    if (data.product_code) setProductCodeValue(data.product_code);

    // Category (no "other" path any more)
    const categorySelect = document.getElementById("category");
    if (categorySelect && data.category) {
      categorySelect.value = data.category;
      if (typeof handleCategoryChange === "function") {
        handleCategoryChange(categorySelect);
      }
    }

    const locationInput = document.getElementById("location_input");
    if (locationInput) {
      locationInput.value = data.locations || data.location_options || data.meetup_locations_list || "";
    }

    const days = (data.available_days || "")
      .split(",")
      .map((d) => d.trim())
      .filter(Boolean);
    document.querySelectorAll(".meetup-day").forEach((cb) => {
      cb.checked = days.includes(cb.value);
    });

    const fromInput = document.getElementById("meetup_time_from");
    const toInput = document.getElementById("meetup_time_to");
    if (fromInput && data.meetup_time_from) {
      fromInput.value = String(data.meetup_time_from).slice(0, 5);
    }
    if (toInput && data.meetup_time_to) {
      toInput.value = String(data.meetup_time_to).slice(0, 5);
    }

    // Pre-order
    const preOrderEl = document.getElementById("is_pre_order");
    if (preOrderEl) preOrderEl.checked = !!data.pre_order;

    // ---------- Restore gallery images ----------
    const container = document.getElementById("image_preview_container");
    if (container) {
      container.innerHTML = "";
      window.existingImageUrls = [];
      window.selectedFiles = [];          // clear any previous new files

      (data.images || []).forEach((img, idx) => {
        window.existingImageUrls.push({ id: img.id, url: img.url, is_main: img.is_main });
        const wrapper = document.createElement("div");
        wrapper.className = "preview-wrapper";
        wrapper.dataset.existing = "1";
        wrapper.dataset.imageId = img.id || "";
        const badge = img.is_main || idx === 0 ? '<span class="main-badge">COVER</span>' : "";
        wrapper.innerHTML = `
          ${badge}
          <img src="${img.url}" class="preview-box ${img.is_main || idx === 0 ? "is-main-image" : ""}">
        `;
        container.appendChild(wrapper);
      });
    }

    // ---------- Restore variants (incl. image index association) ----------
    window.productVariants = (data.variants || []).map((v) => ({
      name: v.variant_name || v.name,
      price: v.price,
      stock: v.stocks || v.stock,
      condition: v.condition || "Brand New",
      attribute: v.attribute_value || v.attribute || v.variant_attribute || "",
      flaws: v.flaws || "",
      imageIndex: v.image_index != null ? v.image_index : null,
      imageUrl: v.image_url || null,          // if backend returns a direct URL
    }));

    if (typeof renderVariantList === "function") {
      renderVariantList();
    }

    // Soft-delete the staged item so the user can re-add the edited version
    await fetch(`/api/staged-product/delete/${stagedId}/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
      },
    });

    const card = document.querySelector(`.staged-item[data-id="${stagedId}"]`);
    if (card) card.remove();

    const countEl = document.getElementById("item_count");
    if (countEl) {
      countEl.innerText = document.querySelectorAll(".staged-item").length;
    }

    // Scroll form into view
    document.getElementById("product_form")?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    console.error("Edit Error:", err);
    Swal.fire("Error", "Could not retrieve product data.", "error");
  }
}

/* ===================== VARIANT HELPERS ===================== */
function renderVariantList() {
  const listContainer = document.getElementById("variant_list");
  if (!listContainer) return;
  listContainer.innerHTML = "";

  (window.productVariants || []).forEach((variant) => {
    const div = document.createElement("div");
    div.className =
      "variant-card d-flex align-items-center p-2 mb-2 rounded shadow-sm border bg-white";

    let thumbHtml = "";
    if (variant.imageUrl) {
      thumbHtml = `<img src="${variant.imageUrl}" style="width:35px;height:35px;object-fit:cover;" class="rounded me-2 border">`;
    } else if (
      variant.imageIndex != null &&
      window.selectedFiles[variant.imageIndex]
    ) {
      const thumbUrl = URL.createObjectURL(window.selectedFiles[variant.imageIndex]);
      thumbHtml = `<img src="${thumbUrl}" style="width:35px;height:35px;object-fit:cover;" class="rounded me-2 border">`;
    } else if (
      variant.imageIndex != null &&
      window.existingImageUrls[variant.imageIndex]
    ) {
      thumbHtml = `<img src="${window.existingImageUrls[variant.imageIndex].url}" style="width:35px;height:35px;object-fit:cover;" class="rounded me-2 border">`;
    }

    div.innerHTML = `
      ${thumbHtml}
      <div class="flex-grow-1">
        <div class="d-flex align-items-center">
          <span class="small fw-bold text-dark">${variant.name}</span>
          ${
            variant.attribute
              ? `<span class="badge bg-secondary-subtle text-secondary ms-2" style="font-size:0.6rem;">${variant.attribute}</span>`
              : ""
          }
          <span class="badge bg-info-subtle text-info ms-1" style="font-size:0.6rem;">${variant.condition || ""}</span>
        </div>
        <div class="text-muted" style="font-size:0.7rem;">
          ₱${variant.price} | Stock: ${variant.stock}
          ${variant.flaws ? ` | <span class="text-danger">Flaw: ${variant.flaws}</span>` : ""}
        </div>
      </div>
      <button type="button" class="btn-close" style="font-size:0.6rem;"
              onclick="removeVariant(this, '${variant.name}')"></button>
    `;
    listContainer.appendChild(div);
  });
  updateTotalStock();
}

function addVariant() {
  const nameInput = document.getElementById("variant_name");
  const priceInput = document.getElementById("variant_price");
  const stockInput = document.getElementById("variant_stock");
  const attrInput = document.getElementById("variant_attribute");
  const flawsInput = document.getElementById("variant_flaws");
  const conditionSelect = document.getElementById("variant_condition");
  const listContainer = document.getElementById("variant_list");

  if (!nameInput || !stockInput || !listContainer) return;

  const variantName = nameInput.value.trim();
  const variantAttr = attrInput ? attrInput.value.trim() : "";
  const stockValue = stockInput.value;

  if (!variantName || !stockValue) {
    Swal.fire("Missing Info", "Please provide a Variant Name and Stock.", "warning");
    return;
  }

  const priceValue = parseFloat(priceInput?.value) || 0;
  const conditionValue = conditionSelect ? conditionSelect.value : "Brand New";
  const flawsValue = flawsInput ? flawsInput.value.trim() : "";

  const variant = {
    name: variantName,
    price: priceValue,
    stock: parseInt(stockValue, 10) || 0,
    attribute: variantAttr,
    condition: conditionValue,
    flaws: flawsValue,
    imageIndex: window.currentSelectedImageIndex,
  };

  if (!window.productVariants) window.productVariants = [];
  window.productVariants.push(variant);

  // Re-render whole list so thumbnails stay consistent
  renderVariantList();

  nameInput.value = "";
  if (attrInput) attrInput.value = "";
  if (priceInput) priceInput.value = "";
  stockInput.value = "";
  if (flawsInput) flawsInput.value = "";
  if (conditionSelect) conditionSelect.value = "Brand New";

  const imgBtn = document.querySelector('[onclick="openVariantImagePicker()"]');
  if (imgBtn) imgBtn.innerHTML = `<i class="bi bi-image me-1"></i> Pick Image`;

  window.currentSelectedImageIndex = null;
}

function openVariantImagePicker() {
  // Combine existing restored images + newly selected files
  const existing = window.existingImageUrls || [];
  const newFiles = window.selectedFiles || [];

  if (existing.length === 0 && newFiles.length === 0) {
    return Swal.fire("No Photos", "Please upload product photos first!", "info");
  }

  let html = '<div class="row g-2">';
  // Existing images first
  existing.forEach((img, index) => {
    html += `
      <div class="col-4">
        <div class="position-relative">
          <img src="${img.url}" class="img-thumbnail cursor-pointer border-2"
               onclick="selectVariantImage(${index}, true)"
               style="height:80px;width:100%;object-fit:cover;">
          ${index === 0 ? '<span class="badge bg-dark position-absolute top-0 start-0 m-1" style="font-size:0.5rem;">Cover</span>' : ""}
        </div>
      </div>`;
  });
  // New files
  newFiles.forEach((file, index) => {
    const url = URL.createObjectURL(file);
    const globalIdx = existing.length + index;
    html += `
      <div class="col-4">
        <div class="position-relative">
          <img src="${url}" class="img-thumbnail cursor-pointer border-2"
               onclick="selectVariantImage(${globalIdx}, false)"
               style="height:80px;width:100%;object-fit:cover;">
        </div>
      </div>`;
  });
  html += "</div>";

  Swal.fire({
    title: "Assign Image to Variant",
    html: html,
    showConfirmButton: false,
    customClass: { popup: "rounded-4" },
  });
}

function selectVariantImage(index, isExisting) {
  window.currentSelectedImageIndex = index;
  const btn = document.querySelector('[onclick="openVariantImagePicker()"]');
  if (btn) {
    btn.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i> Image Selected`;
  }
  Swal.close();
}

function removeVariant(btn, name) {
  window.productVariants = (window.productVariants || []).filter(
    (v) => v.name !== name,
  );
  if (btn && btn.parentElement) btn.parentElement.remove();
  updateTotalStock();
}

function updateTotalStock() {
  const stocksEl = document.getElementById("stocks");
  if (!stocksEl) return;
  const total = (window.productVariants || []).reduce(
    (sum, v) => sum + (v.stock || 0),
    0,
  );
  stocksEl.value = total;
}

/* ===================== PROHIBITED WORDS ===================== */
function validateProhibitedInput(element) {
  if (!element) return false;
  const text = element.value || "";
  const matchedWord = getFoundProhibitedWord(text);
  const errorDiv = document.getElementById(`${element.id}_prohibited_error`);

  if (matchedWord) {
    element.classList.add("is-invalid");
    if (errorDiv) {
      errorDiv.textContent = `Prohibited word detected: "${matchedWord}"`;
      errorDiv.style.display = "block";
    }
    return true;
  } else {
    element.classList.remove("is-invalid");
    if (errorDiv) errorDiv.style.display = "none";
    return false;
  }
}

function getFoundProhibitedWord(text) {
  if (!text || !window.PROHIBITED_WORDS || window.PROHIBITED_WORDS.length === 0) {
    return null;
  }
  const lowerText = text.toLowerCase();
  return (
    window.PROHIBITED_WORDS.find((word) =>
      lowerText.includes(String(word).toLowerCase()),
    ) || null
  );
}

function checkProhibitedContent(text) {
  if (!text || !window.PROHIBITED_WORDS || window.PROHIBITED_WORDS.length === 0) {
    return false;
  }
  const lowerText = text.toLowerCase();
  return window.PROHIBITED_WORDS.some((word) =>
    lowerText.includes(String(word).toLowerCase()),
  );
}

/* ===================== SUBMIT TO ADMIN ===================== */
async function submitToAdmin() {
  const stagedCount = document.querySelectorAll(".staged-item").length;
  if (stagedCount === 0) {
    return Swal.fire({
      title: "Empty List",
      text: "Your staging list is empty! Add items first.",
      icon: "error",
      confirmButtonColor: "#198754",
    });
  }

  // Approval letter still required for officers at final submit
  if (typeof validateApprovalLetter === "function" && !validateApprovalLetter()) {
    return Swal.fire(
      "Letter of Approval Required",
      "Please attach a Letter of Approval (JPG/PNG, max 10 MB).",
      "warning",
    );
  }

  const csrftoken = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
  if (!csrftoken) {
    return Swal.fire("Error", "CSRF Token missing. Check your HTML template!", "error");
  }

  const confirmation = await Swal.fire({
    title: "Submit for Authorization?",
    text: `Are you sure you want to send ${stagedCount} item(s) for review?`,
    icon: "question",
    showCancelButton: true,
    confirmButtonColor: "#198754",
    cancelButtonColor: "#6c757d",
    confirmButtonText: "Yes, submit it!",
    cancelButtonText: "Wait, let me check",
  });
  if (!confirmation.isConfirmed) return;

  Swal.fire({
    title: "Sending to Admin...",
    text: "Moving your items from staging to the authentication queue.",
    allowOutsideClick: false,
    didOpen: () => Swal.showLoading(),
  });

  const formData = new FormData();
  formData.append("action", "submit_staging");
  formData.append("total_products", stagedCount);

  const approvalInput = document.getElementById("approval_letter");
  if (approvalInput && approvalInput.files && approvalInput.files[0]) {
    formData.append("approval_letter", approvalInput.files[0]);
  }

  try {
    const response = await fetch(window.location.href, {
      method: "POST",
      headers: { "X-CSRFToken": csrftoken },
      body: formData,
    });

    const result = await response.json();
    if (result.status === "success") {
      await Swal.fire({
        icon: "success",
        title: "Success!",
        text: "Your items have been sent for review.",
        confirmButtonColor: "#198754",
      });
      window.location.href = result.redirect_url || window.location.pathname;
    } else {
      Swal.fire({
        icon: "error",
        title: "Submission Failed",
        text: result.message || "Failed to save items.",
      });
    }
  } catch (error) {
    console.error("Submission Error:", error);
    Swal.fire({
      icon: "error",
      title: "Connection Error",
      text: "Something went wrong while connecting to the server.",
    });
  }
}

/* ===================== REMOVE STAGED ITEM (persistent) ===================== */
async function removeItem(btn, productId) {
  const card = btn?.closest(".staged-item");

  // Optimistic UI
  if (card) card.remove();
  const remaining = document.querySelectorAll(".staged-item").length;
  const countEl = document.getElementById("item_count");
  if (countEl) countEl.innerText = remaining;
  if (remaining === 0) {
    const stagingArea = document.getElementById("staging_area");
    if (stagingArea) {
      stagingArea.innerHTML =
        '<div class="text-center py-5 text-muted small empty-msg">List is empty.</div>';
    }
  }

  // Persist deletion on server
  try {
    await fetch(`/api/staged-product/delete/${productId}/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
      },
    });
  } catch (err) {
    console.error("Failed to delete staged product on server:", err);
    // Optional: re-add the card or show a toast
  }
}

/* ===================== CATEGORY CHANGE (no "Other") ===================== */
function handleCategoryChange(selectElement) {
  if (!selectElement || selectElement.selectedIndex === -1) {
    const attrSection = document.getElementById("attributes_section");
    if (attrSection) attrSection.classList.add("d-none");
    return;
  }

  const selectedOption = selectElement.options[selectElement.selectedIndex];
  const selectedValue = selectElement.value;
  const selectedText = selectedOption.text.trim();

  const attrSection = document.getElementById("attributes_section");
  const simplePriceSection = document.getElementById("simple_price_section");
  const suggestionContainer = document.getElementById("size_suggestions_container");
  const suggestionButtons = document.getElementById("suggestion_buttons");
  const stocksInput = document.getElementById("stocks");
  const noAttributesNote = document.getElementById("no_attributes_note");

  if (attrSection) attrSection.classList.add("d-none");
  if (suggestionContainer) suggestionContainer.classList.add("d-none");
  if (noAttributesNote) noAttributesNote.classList.add("d-none");
  if (simplePriceSection) simplePriceSection.classList.remove("d-none");
  if (stocksInput) stocksInput.readOnly = false;

  // "other" path completely removed
  if (!selectedValue || selectedValue === "other") return;

  fetch(`/api/get-attributes/${selectedValue}/`)
    .then((response) => response.json())
    .then((data) => {
      // Limit to the 5 most recently used attributes
      let attrs = data.attributes || [];
      if (attrs.length > 5) {
        attrs = attrs.slice(0, 5);          // backend already orders by -created / -id
      }

      if (attrs.length > 0) {
        if (attrSection) attrSection.classList.remove("d-none");
        if (suggestionContainer) suggestionContainer.classList.remove("d-none");
        if (simplePriceSection) simplePriceSection.classList.add("d-none");
        if (stocksInput) stocksInput.readOnly = true;

        if (suggestionButtons) {
          suggestionButtons.innerHTML = "";
          attrs.forEach((attr) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className =
              "btn btn-outline-success btn-sm rounded-pill px-3 suggestion-btn me-2 mb-2";
            btn.innerText = attr.value;
            btn.onclick = function () {
              const variantInput = document.getElementById("variant_name");
              if (variantInput) {
                variantInput.value = attr.value;
                variantInput.focus();
              }
              // Also fill the attribute field for convenience
              const attrField = document.getElementById("variant_attribute");
              if (attrField) attrField.value = attr.value;
            };
            suggestionButtons.appendChild(btn);
          });
        }
      } else {
        const showVariantsFor = [
          "Clothes", "Clothing", "Shoes", "Footwear",
          "Gadgets", "Electronics", "Furniture", "Watches",
        ];
        if (showVariantsFor.includes(selectedText)) {
          if (attrSection) attrSection.classList.remove("d-none");
          if (simplePriceSection) simplePriceSection.classList.add("d-none");
          if (stocksInput) stocksInput.readOnly = true;
          if (noAttributesNote) noAttributesNote.classList.remove("d-none");
        }
      }
    })
    .catch((err) => {
      console.error("Error fetching attributes:", err);
    });
}

function useCustomAttribute() {
  const input = document.getElementById("custom_attribute_input");
  if (!input) return;
  const val = input.value.trim();
  if (!val) return;

  let exists = false;
  document.querySelectorAll("#suggestion_buttons .btn").forEach((btn) => {
    if (btn.innerText === val) {
      exists = true;
      btn.click();
    }
  });

  if (!exists) {
    const variantName = document.getElementById("variant_name");
    if (variantName) variantName.value = val;
    input.value = "";
  }
}

/* ===================== APPROVAL LETTER ===================== */
function previewApprovalLetter(event) {
  const file = event.target.files[0];
  const preview = document.getElementById("approval_preview");
  const errorEl = document.getElementById("approval_letter_error");
  if (!preview || !errorEl) return;

  preview.innerHTML = "";
  errorEl.classList.add("d-none");
  errorEl.textContent = "";

  if (!file) return;

  const okType =
    ["image/jpeg", "image/png"].includes(file.type) ||
    /\.(jpe?g|png)$/i.test(file.name);
  if (!okType) {
    errorEl.textContent = "Only JPG or PNG files are allowed.";
    errorEl.classList.remove("d-none");
    event.target.value = "";
    return;
  }

  if (file.size > 10 * 1024 * 1024) {
    errorEl.textContent = "File exceeds the 10 MB limit.";
    errorEl.classList.remove("d-none");
    event.target.value = "";
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    preview.innerHTML = `
      <a href="${e.target.result}" target="_blank" rel="noopener">
        <img src="${e.target.result}" class="rounded border shadow-sm"
             style="max-width:160px;max-height:120px;object-fit:contain">
      </a>
      <div class="small text-muted mt-1">Click image to view full size</div>`;
  };
  reader.readAsDataURL(file);
}

function validateApprovalLetter() {
  const section = document.getElementById("approval_letter_section");
  if (!section) return true; // management / personal → skip

  const input = document.getElementById("approval_letter");
  const hasExisting = !!document.querySelector(
    '#approval_letter_section img[alt="Current Approval Letter"]',
  );
  if (!hasExisting && (!input || !input.files.length)) {
    const err = document.getElementById("approval_letter_error");
    if (err) {
      err.textContent = "Letter of Approval is required.";
      err.classList.remove("d-none");
    }
    return false;
  }
  return true;
}

/* ===================== GLOBAL LISTENERS ===================== */
document.addEventListener("input", (e) => {
  if (e.target.classList.contains("is-invalid")) {
    e.target.classList.remove("is-invalid");
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const fromInput = document.getElementById("meetup_time_from");
  const toInput = document.getElementById("meetup_time_to");

  if (fromInput) {
    fromInput.addEventListener("change", () => validateMeetupTimeRange(true));
    fromInput.addEventListener("blur", () => validateMeetupTimeRange(true));
  }
  if (toInput) {
    toInput.addEventListener("change", () => validateMeetupTimeRange(true));
    toInput.addEventListener("blur", () => validateMeetupTimeRange(true));
  }

  document.querySelectorAll(".meetup-day").forEach((cb) => {
    cb.addEventListener("change", () => validateMeetupDays(true));
  });
});