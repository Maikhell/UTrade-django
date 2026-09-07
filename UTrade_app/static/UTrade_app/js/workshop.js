if (typeof window.itemCount === "undefined") {
  window.itemCount = 0;
  window.selectedFiles = [];
  window.allStagedProducts = [];
  window.productVariants = [];
  window.currentSelectedImageIndex = null;
  window.PROHIBITED_WORDS = [];
}

async function loadProhibitedWords() {
  try {
    const response = await fetch("/api/prohibited-words/");
    const data = await response.json();
    window.PROHIBITED_WORDS = data.prohibited_words || [];
    console.log("Prohibited words loaded:", window.PROHIBITED_WORDS.length);
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

  container.innerHTML = "";
  window.selectedFiles = Array.from(event.target.files || []);

  window.selectedFiles.forEach((file, index) => {
    const reader = new FileReader();
    reader.onload = function (e) {
      const wrapper = document.createElement("div");
      wrapper.className = "preview-wrapper animate__animated animate__fadeIn";
      const isMain = index === 0;
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

  // Supports "07:30" and "07:30:00"
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
    console.error(
      "Missing time inputs. Need #meetup_time_from and #meetup_time_to in HTML.",
    );
    if (showErrors) {
      Swal.fire(
        "Form Error",
        "Time inputs are missing in the page HTML.",
        "error",
      );
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
  const minAllowed = 7 * 60; // 07:00
  const maxAllowed = 21 * 60; // 21:00

  // Empty
  if (!fromVal) {
    if (showErrors)
      setFieldError(fromInput, "from_time_error", "From time is required.");
    valid = false;
  }
  if (!toVal) {
    if (showErrors)
      setFieldError(toInput, "to_time_error", "To time is required.");
    valid = false;
  }
  if (!valid) return false;

  const fromMins = timeToMinutes(fromVal);
  const toMins = timeToMinutes(toVal);

  if (fromMins === null) {
    if (showErrors)
      setFieldError(fromInput, "from_time_error", "Invalid From time.");
    return false;
  }
  if (toMins === null) {
    if (showErrors) setFieldError(toInput, "to_time_error", "Invalid To time.");
    return false;
  }

  // 7:00 AM – 9:00 PM
  if (fromMins < minAllowed || fromMins > maxAllowed) {
    if (showErrors) {
      setFieldError(
        fromInput,
        "from_time_error",
        "Must be between 7:00 AM and 9:00 PM.",
      );
    }
    valid = false;
  }
  if (toMins < minAllowed || toMins > maxAllowed) {
    if (showErrors) {
      setFieldError(
        toInput,
        "to_time_error",
        "Must be between 7:00 AM and 9:00 PM.",
      );
    }
    valid = false;
  }

  // From < To
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

  // Clear previous invalid states
  [nameEl, priceEl, stocksEl, locationInput, fromInput, toInput].forEach(
    (el) => el && el.classList.remove("is-invalid"),
  );

  let hasError = false;

  // 1. Location (single)
  if (!locationInput || !locationInput.value.trim()) {
    if (locationInput) locationInput.classList.add("is-invalid");
    return Swal.fire(
      "Location Required",
      "Please enter a campus meetup spot.",
      "warning",
    );
  }

  // 2. Available days (multiple)
  if (typeof validateMeetupDays === "function") {
    if (!validateMeetupDays(true)) {
      return Swal.fire(
        "Days Required",
        "Please select at least one available day (Mon–Sat).",
        "warning",
      );
    }
  } else {
    const selectedDaysCheck = getSelectedMeetupDays();
    if (!selectedDaysCheck.length) {
      return Swal.fire(
        "Days Required",
        "Please select at least one available day (Mon–Sat).",
        "warning",
      );
    }
  }

  const selectedDays = getSelectedMeetupDays();

  // 3. Time range
  // Debug (remove later if you want)
  console.log("Time values =>", {
    fromExists: !!fromInput,
    toExists: !!toInput,
    from: fromInput?.value,
    to: toInput?.value,
  });

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
    return Swal.fire(
      "Time Required",
      "Please set both From and To meetup times.",
      "warning",
    );
  }

  // Use improved validator if available
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

  // 4. Name & Description
  if (!nameEl || !nameEl.value.trim()) {
    if (nameEl) nameEl.classList.add("is-invalid");
    hasError = true;
  }

  const isNameInvalid = validateProhibitedInput(nameEl);
  const isDescInvalid = validateProhibitedInput(descEl);

  if (isNameInvalid || isDescInvalid) {
    return Swal.fire(
      "Prohibited Content",
      "Please remove restricted words before proceeding.",
      "error",
    );
  }

  if (
    checkProhibitedContent(nameEl?.value || "") ||
    checkProhibitedContent(descEl?.value || "")
  ) {
    return Swal.fire(
      "Prohibited Content",
      "Your text contains restricted words.",
      "error",
    );
  }

  // 5. Price / Stock / Variants
  let finalPrice, finalStocks;

  if (isVariantMode) {
    if (!window.productVariants || window.productVariants.length === 0) {
      return Swal.fire(
        "Variations Required",
        "Please add at least one variety.",
        "warning",
      );
    }
    finalPrice = window.productVariants[0].price;
    finalStocks = window.productVariants.reduce(
      (sum, v) => sum + (v.stock || 0),
      0,
    );
  } else {
    if (!priceEl || !priceEl.value.trim()) {
      if (priceEl) priceEl.classList.add("is-invalid");
      hasError = true;
    }
    if (!stocksEl || !stocksEl.value.trim()) {
      if (stocksEl) stocksEl.classList.add("is-invalid");
      hasError = true;
    }
    finalPrice = priceEl?.value || 0;
    finalStocks = stocksEl?.value || 0;
  }

  if (!window.selectedFiles || window.selectedFiles.length === 0) {
    return Swal.fire(
      "Photos Required",
      "Please select at least one photo.",
      "warning",
    );
  }

  if (hasError) {
    return Swal.fire(
      "Required Fields",
      "Please fill in the highlighted fields.",
      "error",
    );
  }

  // 6. Category
  let categoryId = categoryEl ? categoryEl.value : "";
  let categoryName = "Uncategorized";
  let customCategoryName = "";

  if (categoryEl && categoryEl.selectedIndex >= 0) {
    categoryName = categoryEl.options[categoryEl.selectedIndex].text;
  }

  if (categoryId === "other") {
    customCategoryName =
      document.getElementById("custom_category")?.value.trim() || "";
    categoryName = customCategoryName || "New Category";
  }

  // 7. FormData
  const formData = new FormData();
  formData.append("name", nameEl.value.trim());
  formData.append("description", descEl?.value.trim() || "");
  formData.append("category", categoryId);
  formData.append("custom_category_name", customCategoryName);
  formData.append("location_options", locationInput.value.trim());
  formData.append("available_days", selectedDays.join(","));
  formData.append("meetup_time_from", fromInput.value);
  formData.append("meetup_time_to", toInput.value);
  formData.append("owner_type", ownerTypeEl?.value || "PERSONAL");

  const paymentEl = document.querySelector('input[name="payment"]:checked');
  formData.append("payment", paymentEl ? paymentEl.value : "BOTH");
  formData.append(
    "pre_order",
    preOrderElement ? preOrderElement.value : "False",
  );
  formData.append("variants", JSON.stringify(window.productVariants || []));

  window.selectedFiles.forEach((file) => {
    formData.append("images", file);
  });

  // 8. AJAX
  Swal.fire({
    title: "Saving to Staging...",
    allowOutsideClick: false,
    didOpen: () => Swal.showLoading(),
  });

  try {
    const response = await fetch("/api/staged-product/add/", {
      method: "POST",
      headers: {
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
          .value,
      },
      body: formData,
    });

    const result = await response.json();

    if (result.status !== "success") {
      throw new Error(result.message || "Server error.");
    }

    const dbId = result.staged_id;

    // 9. UI card
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
            </div>
          </div>
        </div>
        <div class="small text-muted mb-2 text-truncate-2" style="font-size:0.85rem;">${descEl?.value || ""}</div>
        <div class="d-flex flex-wrap gap-1 mb-2">
          <span class="badge bg-light text-dark border fw-normal">
            <i class="bi bi-tag me-1"></i>${categoryName}
          </span>
          <span class="badge bg-light text-dark border fw-normal">
            <i class="bi bi-geo-alt me-1"></i>${locationInput.value.trim()}
          </span>
          <span class="badge bg-light text-dark border fw-normal">
            <i class="bi bi-calendar-week me-1"></i>${daysLabel}
          </span>
          <span class="badge bg-light text-dark border fw-normal">
            <i class="bi bi-clock me-1"></i>${timeLabel}
          </span>
        </div>
      </div>`;

    const stagingArea = document.getElementById("staging_area");
    if (stagingArea) {
      if (stagingArea.querySelector(".empty-msg")) stagingArea.innerHTML = "";
      stagingArea.insertAdjacentHTML("afterbegin", itemCard);
    }

    const countEl = document.getElementById("item_count");
    if (countEl) {
      countEl.innerText = document.querySelectorAll(".staged-item").length;
    }

    // 10. Cleanup
    document.getElementById("product_form")?.reset();
    window.selectedFiles = [];
    window.productVariants = [];
    window.currentSelectedImageIndex = null;

    // Uncheck all day checkboxes after reset
    document.querySelectorAll(".meetup-day").forEach((cb) => {
      cb.checked = false;
    });

    const previewContainer = document.getElementById("image_preview_container");
    if (previewContainer) {
      previewContainer.innerHTML = `
        <div class="text-center py-5 text-muted small w-100">Item added successfully.</div>`;
    }

    const variantList = document.getElementById("variant_list");
    if (variantList) variantList.innerHTML = "";

    if (categoryEl) {
      categoryEl.value = "";
      if (typeof handleCategoryChange === "function") {
        handleCategoryChange(categoryEl);
      }
    }

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
    Swal.fire(
      "Error",
      error.message || "Failed to connect to server.",
      "error",
    );
  }
}

                                  /* ===================== EDIT STAGED ITEM ===================== */
async function editItem(stagedId) {
  try {
    const response = await fetch(`/api/staged-product/${stagedId}/`);
    const data = await response.json();

    if (data.error) throw new Error(data.error);

    // 1. Basic fields
    const nameEl = document.getElementById("name");
    const descEl = document.getElementById("description");
    if (nameEl) nameEl.value = data.name || "";
    if (descEl) descEl.value = data.description || "";

    // 2. Category
    const categorySelect = document.getElementById("category");
    const customCategoryDiv = document.getElementById("other_category_div");
    const customCategoryInput = document.getElementById("custom_category");

    if (categorySelect) {
      const optionExists = Array.from(categorySelect.options).some(
        (opt) => opt.value == data.category,
      );

      if (optionExists) {
        categorySelect.value = data.category;
        if (customCategoryDiv) customCategoryDiv.classList.add("d-none");
      } else {
        categorySelect.value = "other";
        if (customCategoryDiv) {
          customCategoryDiv.classList.remove("d-none");
          if (customCategoryInput) {
            customCategoryInput.value = data.category_name || "";
          }
        }
      }

      if (typeof handleCategoryChange === "function") {
        handleCategoryChange(categorySelect);
      }
    }

    // 3. Single Location
    const locationInput = document.getElementById("location_input");
    if (locationInput) {
      locationInput.value = data.locations || data.location_options || "";
    }

    // 4. Available Days
    const days = (data.available_days || "")
      .split(",")
      .map((d) => d.trim())
      .filter(Boolean);

    document.querySelectorAll(".meetup-day").forEach((cb) => {
      cb.checked = days.includes(cb.value);
    });

    // 5. Time Range
    const fromInput = document.getElementById("meetup_time_from");
    const toInput = document.getElementById("meetup_time_to");
    if (fromInput && data.meetup_time_from) {
      fromInput.value = String(data.meetup_time_from).slice(0, 5);
    }
    if (toInput && data.meetup_time_to) {
      toInput.value = String(data.meetup_time_to).slice(0, 5);
    }

    // 6. Images
    const container = document.getElementById("image_preview_container");
    if (container) {
      container.innerHTML = "";
      (data.images || []).forEach((img) => {
        container.insertAdjacentHTML(
          "beforeend",
          `
          <div class="preview-wrapper">
            <img src="${img.url}" class="preview-box ${img.is_main ? "is-main-image" : ""}">
          </div>`,
        );
      });
    }

    // 7. Variants
    window.productVariants = (data.variants || []).map((v) => ({
      name: v.variant_name || v.name,
      price: v.price,
      stock: v.stocks || v.stock,
      condition: v.condition || "Brand New",
      attribute: v.attribute_value || v.attribute || "",
      flaws: v.flaws || "",
    }));

    if (typeof renderVariantList === "function") {
      renderVariantList();
    }

    // 8. Remove from staging after loading into form
    await fetch(`/api/staged-product/delete/${stagedId}/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
          .value,
      },
    });

    const card = document.querySelector(`.staged-item[data-id="${stagedId}"]`);
    if (card) card.remove();

    const countEl = document.getElementById("item_count");
    if (countEl) {
      countEl.innerText = document.querySelectorAll(".staged-item").length;
    }
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
    div.innerHTML = `
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
        </div>
      </div>
      <button type="button" class="btn-close" style="font-size:0.6rem;"
              onclick="removeVariant(this, '${variant.name}')"></button>
    `;
    listContainer.appendChild(div);
  });
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
    Swal.fire(
      "Missing Info",
      "Please provide a Variant Name and Stock.",
      "warning",
    );
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

  const div = document.createElement("div");
  div.className =
    "variant-card d-flex align-items-center p-2 mb-2 rounded shadow-sm border bg-white animate__animated animate__fadeInUp";

  let thumbHtml = "";
  if (
    window.currentSelectedImageIndex !== null &&
    window.selectedFiles[window.currentSelectedImageIndex]
  ) {
    const thumbUrl = URL.createObjectURL(
      window.selectedFiles[window.currentSelectedImageIndex],
    );
    thumbHtml = `<img src="${thumbUrl}" style="width:35px;height:35px;object-fit:cover;" class="rounded me-2 border">`;
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
        <span class="badge bg-info-subtle text-info ms-1" style="font-size:0.6rem;">${variant.condition}</span>
      </div>
      <div class="text-muted" style="font-size:0.7rem;">
        ₱${variant.price.toFixed(2)} | Stock: ${variant.stock}
        ${variant.flaws ? ` | <span class="text-danger">Flaw: ${variant.flaws}</span>` : ""}
      </div>
    </div>
    <button type="button" class="btn-close" style="font-size:0.6rem;"
            onclick="removeVariant(this, '${variant.name}')"></button>
  `;
  listContainer.appendChild(div);

  nameInput.value = "";
  if (attrInput) attrInput.value = "";
  if (priceInput) priceInput.value = "";
  stockInput.value = "";
  if (flawsInput) flawsInput.value = "";
  if (conditionSelect) conditionSelect.value = "Brand New";

  const imgBtn = document.querySelector('[onclick="openVariantImagePicker()"]');
  if (imgBtn) imgBtn.innerHTML = `<i class="bi bi-image me-1"></i> Pick Image`;

  window.currentSelectedImageIndex = null;
  updateTotalStock();
}

function openVariantImagePicker() {
  if (!window.selectedFiles || window.selectedFiles.length === 0) {
    return Swal.fire(
      "No Photos",
      "Please upload product photos first!",
      "info",
    );
  }

  let html = '<div class="row g-2">';
  window.selectedFiles.forEach((file, index) => {
    const url = URL.createObjectURL(file);
    html += `
      <div class="col-4">
        <div class="position-relative">
          <img src="${url}" class="img-thumbnail cursor-pointer border-2"
               onclick="selectVariantImage(${index})"
               style="height:80px;width:100%;object-fit:cover;">
          ${
            index === 0
              ? '<span class="badge bg-dark position-absolute top-0 start-0 m-1" style="font-size:0.5rem;">Cover</span>'
              : ""
          }
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

function selectVariantImage(index) {
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
  if (
    !text ||
    !window.PROHIBITED_WORDS ||
    window.PROHIBITED_WORDS.length === 0
  ) {
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
  if (
    !text ||
    !window.PROHIBITED_WORDS ||
    window.PROHIBITED_WORDS.length === 0
  ) {
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

  const csrftoken = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
  if (!csrftoken) {
    return Swal.fire(
      "Error",
      "CSRF Token missing. Check your HTML template!",
      "error",
    );
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

/* ===================== REMOVE STAGED ITEM ===================== */
function removeItem(btn, productId) {
  const card = btn?.closest(".staged-item");
  if (card) card.remove();

  window.allStagedProducts = (window.allStagedProducts || []).filter(
    (item) => item.id !== productId,
  );
  window.itemCount = document.querySelectorAll(".staged-item").length;

  const countEl = document.getElementById("item_count");
  if (countEl) countEl.innerText = window.itemCount;

  if (window.itemCount === 0) {
    const stagingArea = document.getElementById("staging_area");
    if (stagingArea) {
      stagingArea.innerHTML =
        '<div class="text-center py-5 text-muted small empty-msg">List is empty.</div>';
    }
  }
}

/* ===================== CATEGORY CHANGE ===================== */
function handleCategoryChange(selectElement) {
  if (!selectElement || selectElement.selectedIndex === -1) {
    const attrSection = document.getElementById("attributes_section");
    const otherDiv = document.getElementById("other_category_div");
    if (attrSection) attrSection.classList.add("d-none");
    if (otherDiv) otherDiv.classList.add("d-none");
    return;
  }

  const selectedOption = selectElement.options[selectElement.selectedIndex];
  const selectedValue = selectElement.value;
  const selectedText = selectedOption.text.trim();

  const attrSection = document.getElementById("attributes_section");
  const otherDiv = document.getElementById("other_category_div");
  const simplePriceSection = document.getElementById("simple_price_section");
  const suggestionContainer = document.getElementById(
    "size_suggestions_container",
  );
  const suggestionButtons = document.getElementById("suggestion_buttons");
  const stocksInput = document.getElementById("stocks");
  const noAttributesNote = document.getElementById("no_attributes_note");

  if (attrSection) attrSection.classList.add("d-none");
  if (otherDiv) otherDiv.classList.add("d-none");
  if (suggestionContainer) suggestionContainer.classList.add("d-none");
  if (noAttributesNote) noAttributesNote.classList.add("d-none");
  if (simplePriceSection) simplePriceSection.classList.remove("d-none");
  if (stocksInput) stocksInput.readOnly = false;

  if (selectedValue === "other") {
    if (otherDiv) otherDiv.classList.remove("d-none");
    if (attrSection) attrSection.classList.remove("d-none");
    if (noAttributesNote) noAttributesNote.classList.remove("d-none");
    if (simplePriceSection) simplePriceSection.classList.add("d-none");
    if (stocksInput) stocksInput.readOnly = true;
    return;
  }

  fetch(`/api/get-attributes/${selectedValue}/`)
    .then((response) => response.json())
    .then((data) => {
      if (data.attributes && data.attributes.length > 0) {
        if (attrSection) attrSection.classList.remove("d-none");
        if (suggestionContainer) suggestionContainer.classList.remove("d-none");
        if (simplePriceSection) simplePriceSection.classList.add("d-none");
        if (stocksInput) stocksInput.readOnly = true;

        if (suggestionButtons) {
          suggestionButtons.innerHTML = "";
          data.attributes.forEach((attr) => {
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
            };
            suggestionButtons.appendChild(btn);
          });
        }
      } else {
        const showVariantsFor = [
          "Clothes",
          "Clothing",
          "Shoes",
          "Footwear",
          "Gadgets",
          "Electronics",
          "Furniture",
          "Watches",
        ];
        if (showVariantsFor.includes(selectedText)) {
          if (attrSection) attrSection.classList.remove("d-none");
          if (simplePriceSection) simplePriceSection.classList.add("d-none");
          if (stocksInput) stocksInput.readOnly = true;
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
    fromInput.addEventListener("change", validateMeetupTimeRange);
    fromInput.addEventListener("blur", validateMeetupTimeRange);
  }
  if (toInput) {
    toInput.addEventListener("change", validateMeetupTimeRange);
    toInput.addEventListener("blur", validateMeetupTimeRange);
  }
});
