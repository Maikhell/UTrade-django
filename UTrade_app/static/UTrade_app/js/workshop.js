/* ===================================================================
   Seller workshop: add products
   =================================================================== */

if (typeof window.itemCount === "undefined") {
  window.itemCount = 0;
  window.selectedFiles = []; // the cover photo: [File] or []
  window.allStagedProducts = [];
  window.productVariants = []; // { name, sizes[], price, stock, imageFile, imageUrl, keepFrom }
  window.PROHIBITED_WORDS = [];
  window.existingCover = null; // { id, url } while editing and the cover is unchanged
  window.editingStagedId = null;
  window.sizeChart = null; // { columns: [], rows: [{ size, values: [] }] }
  window.sizeDraft = { columns: [], rows: [] }; // working copy inside the size table dialog
  window.currentSizes = []; // size chips in the variation form
  window.variantImageFile = null; // a newly chosen image in the variation form
  window.variantImageKeep = null; // { url, keepFrom }: the saved image of the variation being edited
  window.editingVariantIndex = null; // index of the variation being edited in the form
  // Session flag for approval letter (true if already on file or uploaded this session)
  window.approvalLetterOnFile = !!document.querySelector(
    '#approval_letter_section img[alt="Current Approval Letter"]'
  );
}

var MAX_IMAGE_BYTES = 10 * 1024 * 1024;
var SIZE_PRESETS = [
  "Height (cm)", "Weight (kg)", "Chest (cm)", "Waist (cm)", "Hips (cm)",
  "Shoulder (cm)", "Sleeve (cm)", "Length (cm)", "Foot length (cm)",
];
var SIZE_LIMITS = { rows: 20, cols: 8 };
var EMPTY_VARIANT_FORM = JSON.stringify(["", "", "", [], ""]);

/* ===================== SMALL HELPERS ===================== */
function escapeHtml(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

function csrfToken() {
  var el = document.querySelector("[name=csrfmiddlewaretoken]");
  return el ? el.value : "";
}

function normalizeSize(raw) {
  return String(raw || "").trim().replace(/\s+/g, " ").slice(0, 20);
}

function splitSizes(text) {
  return String(text || "").split(",").map(normalizeSize).filter(Boolean);
}

function checkImageFile(file, label) {
  if (!file) return false;
  var okType =
    /^image\/(jpeg|png|webp)$/i.test(file.type) || /\.(jpe?g|png|webp)$/i.test(file.name);
  if (!okType) {
    Swal.fire("Invalid file", label + " must be a JPG, PNG or WEBP image.", "warning");
    return false;
  }
  if (file.size > MAX_IMAGE_BYTES) {
    Swal.fire("File too large", label + " exceeds the 10 MB limit.", "warning");
    return false;
  }
  return true;
}

function isBlobUrl(url) {
  return typeof url === "string" && url.indexOf("blob:") === 0;
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

/* ===================== PRODUCT COVER (one photo) ===================== */
function coverEmptyHtml() {
  return (
    '<div class="ap-empty"><i class="bi bi-cloud-upload"></i>' +
    "<span>No cover photo selected yet</span></div>"
  );
}

function renderCover(src) {
  var container = document.getElementById("image_preview_container");
  if (!container) return;
  container.innerHTML =
    '<div class="preview-wrapper">' +
    '<span class="main-badge">COVER</span>' +
    '<img src="' + escapeHtml(src) + '" class="preview-box is-main-image" alt="Cover photo">' +
    '<button type="button" class="ap-cover-remove" onclick="removeCover()" ' +
    'aria-label="Remove cover photo"><i class="bi bi-x-lg"></i></button>' +
    "</div>";
}

function previewCover(event) {
  var input = event.target;
  var file = input.files && input.files[0];
  if (!file) return;
  if (!checkImageFile(file, "The cover photo")) {
    input.value = "";
    return;
  }
  window.selectedFiles = [file];
  window.existingCover = null;
  var reader = new FileReader();
  reader.onload = function (e) {
    renderCover(e.target.result);
  };
  reader.readAsDataURL(file);
}

function removeCover() {
  window.selectedFiles = [];
  window.existingCover = null;
  var input = document.getElementById("image_input");
  if (input) input.value = "";
  var container = document.getElementById("image_preview_container");
  if (container) container.innerHTML = coverEmptyHtml();
}

/* ===================== AVAILABLE SIZES (chips) ===================== */
function renderSizeChips() {
  var box = document.getElementById("variant_sizes_chips");
  if (!box) return;
  box.innerHTML = window.currentSizes
    .map(function (size, i) {
      return (
        '<span class="ap-chip">' + escapeHtml(size) +
        '<button type="button" class="ap-chip-x" onclick="removeSizeChip(' + i + ')" ' +
        'aria-label="Remove ' + escapeHtml(size) + '"><i class="bi bi-x"></i></button></span>'
      );
    })
    .join("");
}

function addSizeChip(raw) {
  splitSizes(raw).forEach(function (size) {
    var exists = window.currentSizes.some(function (s) {
      return s.toLowerCase() === size.toLowerCase();
    });
    if (!exists) window.currentSizes.push(size);
  });
  renderSizeChips();
}

function removeSizeChip(index) {
  window.currentSizes.splice(index, 1);
  renderSizeChips();
}

function commitSizeInput() {
  var input = document.getElementById("variant_size_input");
  if (!input) return;
  if (input.value.trim()) addSizeChip(input.value);
  input.value = "";
}

function handleSizeKey(event) {
  if (event.key === "Enter" || event.key === ",") {
    event.preventDefault();
    commitSizeInput();
  } else if (event.key === "Backspace" && !event.target.value && window.currentSizes.length) {
    window.currentSizes.pop();
    renderSizeChips();
  }
}

/* ===================== VARIANT IMAGE ===================== */
function resetVariantImageUi() {
  var input = document.getElementById("variant_image_input");
  if (input) input.value = "";
  var preview = document.getElementById("variant_image_preview");
  if (preview) preview.innerHTML = '<i class="bi bi-image"></i>';
  var clear = document.getElementById("variant_image_clear");
  if (clear) clear.classList.add("d-none");
}

function showVariantImagePreview(src) {
  var preview = document.getElementById("variant_image_preview");
  if (preview) preview.innerHTML = '<img src="' + escapeHtml(src) + '" alt="">';
  var clear = document.getElementById("variant_image_clear");
  if (clear) clear.classList.remove("d-none");
}

function clearVariantImage() {
  window.variantImageFile = null;
  window.variantImageKeep = null;
  resetVariantImageUi();
}

function previewVariantImage(event) {
  var input = event.target;
  var file = input.files && input.files[0];
  if (!file) return;
  if (!checkImageFile(file, "The variant image")) {
    input.value = "";
    return;
  }
  window.variantImageFile = file;
  window.variantImageKeep = null;
  var reader = new FileReader();
  reader.onload = function (e) {
    showVariantImagePreview(e.target.result);
  };
  reader.readAsDataURL(file);
}

/* ===================== VARIANTS ===================== */
function variantFormSnapshot() {
  function val(id) {
    var el = document.getElementById(id);
    return el ? el.value.trim() : "";
  }
  var sizes = window.currentSizes.concat(splitSizes(val("variant_size_input")));
  var image = window.variantImageFile
    ? "new:" + window.variantImageFile.name + ":" + window.variantImageFile.size
    : window.variantImageKeep
      ? "keep:" + window.variantImageKeep.keepFrom
      : "";
  return JSON.stringify([val("variant_name"), val("variant_price"), val("variant_stock"), sizes, image]);
}

function variantSnapshot(v) {
  var image = v.imageFile
    ? "new:" + v.imageFile.name + ":" + v.imageFile.size
    : v.keepFrom
      ? "keep:" + v.keepFrom
      : "";
  return JSON.stringify([v.name, String(v.price), String(v.stock), v.sizes || [], image]);
}

/** True when the variation form holds changes that haven't been saved/added yet. */
function isVariantFormDirty() {
  var current = variantFormSnapshot();
  if (window.editingVariantIndex !== null) {
    var editing = window.productVariants[window.editingVariantIndex];
    return !editing || current !== variantSnapshot(editing);
  }
  return current !== EMPTY_VARIANT_FORM;
}

function setVariantFormMode(variantName) {
  var editing = variantName != null;
  var note = document.getElementById("variant_editing_note");
  var noteName = document.getElementById("variant_editing_name");
  var cancel = document.getElementById("variant_cancel_btn");
  var label = document.getElementById("variant_submit_label");
  var icon = document.getElementById("variant_submit_icon");
  if (note) note.classList.toggle("d-none", !editing);
  if (noteName) noteName.textContent = editing ? variantName : "";
  if (cancel) cancel.classList.toggle("d-none", !editing);
  if (label) label.textContent = editing ? "Save changes" : "Add Variant";
  if (icon) icon.className = editing ? "bi bi-check-circle me-1" : "bi bi-plus-circle me-1";
}

function resetVariantForm() {
  window.editingVariantIndex = null;
  ["variant_name", "variant_price", "variant_stock", "variant_size_input"].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) {
      el.value = "";
      el.classList.remove("is-invalid");
    }
  });
  window.currentSizes = [];
  renderSizeChips();
  clearVariantImage();
  setVariantFormMode(null);
}

function renderVariantList() {
  var list = document.getElementById("variant_list");
  if (!list) return;
  list.innerHTML = "";

  (window.productVariants || []).forEach(function (variant, index) {
    var div = document.createElement("div");
    var editing = window.editingVariantIndex === index;
    div.className =
      "variant-card d-flex align-items-center p-2 mb-2 rounded shadow-sm border bg-white" +
      (editing ? " is-editing" : "");

    var thumb = variant.imageUrl
      ? '<img src="' + escapeHtml(variant.imageUrl) + '" class="ap-vthumb rounded me-2 border" alt="">'
      : '<span class="ap-vthumb ap-vthumb-empty rounded me-2 border"><i class="bi bi-image"></i></span>';

    var sizes = (variant.sizes || [])
      .map(function (s) {
        return '<span class="ap-vsize">' + escapeHtml(s) + "</span>";
      })
      .join("");

    div.innerHTML =
      thumb +
      '<div class="flex-grow-1 ap-vinfo">' +
      '<div class="small fw-bold text-dark">' + escapeHtml(variant.name) + "</div>" +
      (sizes ? '<div class="ap-vsizes">' + sizes + "</div>" : "") +
      '<div class="text-muted" style="font-size:0.75rem;">₱' +
      Number(variant.price).toFixed(2) + " | Stock: " + variant.stock + "</div>" +
      "</div>" +
      '<button type="button" class="btn btn-sm text-success p-1 me-1" ' +
      'aria-label="Edit ' + escapeHtml(variant.name) + '" onclick="editVariant(' + index + ')">' +
      '<i class="bi bi-pencil-square"></i></button>' +
      '<button type="button" class="btn-close" style="font-size:0.6rem;" ' +
      'aria-label="Remove ' + escapeHtml(variant.name) + '" onclick="removeVariant(' + index + ')"></button>';
    list.appendChild(div);
  });
  updateTotalStock();
}

/** Add a new variation, or save changes to the one being edited. */
function addVariant() {
  commitSizeInput(); // include a size that was typed but not confirmed yet

  var nameInput = document.getElementById("variant_name");
  var priceInput = document.getElementById("variant_price");
  var stockInput = document.getElementById("variant_stock");
  if (!nameInput || !priceInput || !stockInput) return;

  var name = nameInput.value.trim();
  if (!name || stockInput.value === "") {
    Swal.fire("Missing Info", "Please provide a Variation Name and Stock.", "warning");
    return;
  }

  var price = parseFloat(priceInput.value);
  if (!(price > 0)) {
    priceInput.classList.add("is-invalid");
    priceInput.focus();
    Swal.fire("Price Required", "Please enter a price greater than 0 for this variation.", "warning");
    return;
  }

  var stock = parseInt(stockInput.value, 10);
  if (Number.isNaN(stock) || stock < 0) {
    stockInput.classList.add("is-invalid");
    Swal.fire("Invalid Stock", "Stock must be 0 or more.", "warning");
    return;
  }

  var editIndex = window.editingVariantIndex;
  var duplicate = (window.productVariants || []).some(function (v, i) {
    return i !== editIndex && v.name.toLowerCase() === name.toLowerCase();
  });
  if (duplicate) {
    Swal.fire("Already Added", "A variation with this name already exists.", "warning");
    return;
  }

  var sizes = window.currentSizes.slice();
  if (sizes.join(", ").length > 100) {
    Swal.fire("Too Many Sizes", "Keep the sizes list under 100 characters.", "warning");
    return;
  }

  var previous = editIndex !== null ? window.productVariants[editIndex] : null;

  // Image: a new file, the saved image of the variation being edited, or none
  var imageFile = window.variantImageFile;
  var imageUrl = null;
  var keepFrom = null;
  if (imageFile) {
    imageUrl =
      previous && previous.imageFile === imageFile ? previous.imageUrl : URL.createObjectURL(imageFile);
  } else if (window.variantImageKeep) {
    imageUrl = window.variantImageKeep.url;
    keepFrom = window.variantImageKeep.keepFrom;
  }

  // Free the old preview if it was replaced or removed
  if (previous && previous.imageFile && previous.imageFile !== imageFile && isBlobUrl(previous.imageUrl)) {
    URL.revokeObjectURL(previous.imageUrl);
  }

  var variant = {
    name: name,
    sizes: sizes,
    price: price,
    stock: stock,
    imageFile: imageFile,
    imageUrl: imageUrl,
    keepFrom: keepFrom,
  };

  if (previous) {
    window.productVariants[editIndex] = variant;
    Swal.fire({
      toast: true,
      position: "top-end",
      icon: "success",
      title: "Variation updated",
      showConfirmButton: false,
      timer: 1500,
    });
  } else {
    window.productVariants.push(variant);
  }

  resetVariantForm();
  renderVariantList();
  nameInput.focus({ preventScroll: true });
}

/** Load a variation back into the form so it can be changed. */
async function editVariant(index) {
  var variant = (window.productVariants || [])[index];
  if (!variant || window.editingVariantIndex === index) return;

  if (isVariantFormDirty()) {
    var switching = window.editingVariantIndex !== null;
    var answer = await Swal.fire({
      title: switching ? "Discard your changes?" : "Replace what you've typed?",
      text: switching
        ? "You have unsaved changes to the variation you were editing."
        : "The variation you started typing hasn't been added yet.",
      icon: "question",
      showCancelButton: true,
      confirmButtonColor: "#198754",
      confirmButtonText: "Edit this one",
      cancelButtonText: "Keep typing",
    });
    if (!answer.isConfirmed) return;
  }

  window.editingVariantIndex = index;

  var nameEl = document.getElementById("variant_name");
  var priceEl = document.getElementById("variant_price");
  var stockEl = document.getElementById("variant_stock");
  var sizeInput = document.getElementById("variant_size_input");
  [nameEl, priceEl, stockEl].forEach(function (el) {
    if (el) el.classList.remove("is-invalid");
  });
  if (nameEl) nameEl.value = variant.name;
  if (priceEl) priceEl.value = variant.price;
  if (stockEl) stockEl.value = variant.stock;
  if (sizeInput) sizeInput.value = "";

  window.currentSizes = (variant.sizes || []).slice();
  renderSizeChips();

  window.variantImageFile = variant.imageFile || null;
  window.variantImageKeep =
    !variant.imageFile && variant.keepFrom && variant.imageUrl
      ? { url: variant.imageUrl, keepFrom: variant.keepFrom }
      : null;
  resetVariantImageUi();
  if (variant.imageUrl) showVariantImagePreview(variant.imageUrl);

  setVariantFormMode(variant.name);
  renderVariantList();

  if (nameEl) {
    nameEl.scrollIntoView({ behavior: "smooth", block: "center" });
    nameEl.focus({ preventScroll: true });
  }
}

function cancelVariantEdit() {
  resetVariantForm();
  renderVariantList();
}

function removeVariant(index) {
  var removed = window.productVariants[index];
  if (removed && removed.imageFile && isBlobUrl(removed.imageUrl)) {
    URL.revokeObjectURL(removed.imageUrl);
  }
  window.productVariants.splice(index, 1);

  if (window.editingVariantIndex === index) {
    resetVariantForm(); // the variation being edited is gone
  } else if (window.editingVariantIndex !== null && window.editingVariantIndex > index) {
    window.editingVariantIndex -= 1;
  }
  renderVariantList();
}

function updateTotalStock() {
  var stocksEl = document.getElementById("stocks");
  if (!stocksEl) return;
  var total = (window.productVariants || []).reduce(function (sum, v) {
    return sum + (v.stock || 0);
  }, 0);
  stocksEl.value = total;
}

function forceVariationMode() {
  var attr = document.getElementById("attributes_section");
  var simple = document.getElementById("simple_price_section");
  var stocks = document.getElementById("stocks");
  if (attr) attr.classList.remove("d-none");
  if (simple) simple.classList.add("d-none");
  if (stocks) stocks.readOnly = true;
}

/* ===================== SIZE TABLE (measurements per size) ===================== */
function cloneChart(chart) {
  if (!chart || !Array.isArray(chart.columns) || !Array.isArray(chart.rows)) {
    return { columns: [], rows: [] };
  }
  return {
    columns: chart.columns.slice(),
    rows: chart.rows.map(function (r) {
      return { size: r.size, values: (r.values || []).slice() };
    }),
  };
}

function setSizeMsg(text) {
  var el = document.getElementById("size_table_msg");
  if (!el) return;
  if (!text) {
    el.classList.add("d-none");
    el.textContent = "";
  } else {
    el.textContent = text;
    el.classList.remove("d-none");
  }
}

function pushDraftRow(size) {
  size = normalizeSize(size);
  if (!size) return false;
  var d = window.sizeDraft;
  var exists = d.rows.some(function (r) {
    return r.size.toLowerCase() === size.toLowerCase();
  });
  if (exists) return false;
  if (d.rows.length >= SIZE_LIMITS.rows) {
    setSizeMsg("You can add up to " + SIZE_LIMITS.rows + " sizes.");
    return false;
  }
  d.rows.push({ size: size, values: d.columns.map(function () { return ""; }) });
  return true;
}

function collectKnownSizes() {
  var sizes = [];
  (window.productVariants || []).forEach(function (v) {
    (v.sizes || []).forEach(function (s) { sizes.push(s); });
  });
  (window.currentSizes || []).forEach(function (s) { sizes.push(s); });
  return sizes;
}

function initSizeDraft() {
  window.sizeDraft = cloneChart(window.sizeChart);
  setSizeMsg("");
  collectKnownSizes().forEach(function (s) { pushDraftRow(s); });
  renderSizeTable();
}

function addColumn(name) {
  name = String(name || "").trim().replace(/\s+/g, " ").slice(0, 30);
  if (!name) return false;
  var d = window.sizeDraft;
  var exists = d.columns.some(function (c) { return c.toLowerCase() === name.toLowerCase(); });
  if (exists) return false;
  if (d.columns.length >= SIZE_LIMITS.cols) {
    setSizeMsg("You can add up to " + SIZE_LIMITS.cols + " measurements.");
    return false;
  }
  d.columns.push(name);
  d.rows.forEach(function (r) { r.values.push(""); });
  return true;
}

function removeColumn(index) {
  var d = window.sizeDraft;
  d.columns.splice(index, 1);
  d.rows.forEach(function (r) { r.values.splice(index, 1); });
  setSizeMsg("");
  renderSizeTable();
}

function togglePresetColumn(presetIndex) {
  var name = SIZE_PRESETS[presetIndex];
  var d = window.sizeDraft;
  var at = d.columns.findIndex(function (c) { return c.toLowerCase() === name.toLowerCase(); });
  setSizeMsg("");
  if (at >= 0) removeColumn(at);
  else {
    addColumn(name);
    renderSizeTable();
  }
}

function addCustomColumn() {
  var input = document.getElementById("size_custom_column");
  if (!input) return;
  setSizeMsg("");
  if (addColumn(input.value)) input.value = "";
  renderSizeTable();
}

function addSizeRow() {
  var input = document.getElementById("size_new_row");
  if (!input) return;
  setSizeMsg("");
  input.value.split(",").forEach(function (s) { pushDraftRow(s); });
  input.value = "";
  renderSizeTable();
}

function removeSizeRow(index) {
  window.sizeDraft.rows.splice(index, 1);
  setSizeMsg("");
  renderSizeTable();
}

function onSizeLabelInput(rowIndex, value) {
  window.sizeDraft.rows[rowIndex].size = String(value || "").slice(0, 20);
}

function onSizeCellInput(rowIndex, colIndex, value) {
  window.sizeDraft.rows[rowIndex].values[colIndex] = String(value || "").slice(0, 20);
}

function renderSizeTable() {
  var d = window.sizeDraft;

  var presets = document.getElementById("size_presets");
  if (presets) {
    presets.innerHTML = SIZE_PRESETS.map(function (name, i) {
      var active = d.columns.some(function (c) { return c.toLowerCase() === name.toLowerCase(); });
      return (
        '<button type="button" class="btn btn-sm rounded-pill ' +
        (active ? "btn-success" : "btn-outline-success") +
        '" onclick="togglePresetColumn(' + i + ')">' +
        (active ? '<i class="bi bi-check-lg me-1"></i>' : "") + escapeHtml(name) + "</button>"
      );
    }).join("");
  }

  var host = document.getElementById("size_table_host");
  if (!host) return;

  if (!d.columns.length) {
    host.innerHTML =
      '<div class="ap-st-empty">Pick the measurements you want to show above (height, weight, chest…).</div>';
    return;
  }
  if (!d.rows.length) {
    host.innerHTML =
      '<div class="ap-st-empty">No sizes yet. Add sizes to your variations, or add one below.</div>';
    return;
  }

  var head =
    "<th>Size</th>" +
    d.columns.map(function (c, i) {
      return (
        "<th>" + escapeHtml(c) +
        ' <button type="button" class="ap-st-th-x" onclick="removeColumn(' + i + ')" ' +
        'aria-label="Remove ' + escapeHtml(c) + '"><i class="bi bi-x-circle-fill"></i></button></th>'
      );
    }).join("") +
    "<th></th>";

  var body = d.rows.map(function (row, r) {
    var cells = d.columns.map(function (c, ci) {
      return (
        '<td><input type="text" class="form-control form-control-sm" maxlength="20" value="' +
        escapeHtml(row.values[ci] || "") + '" oninput="onSizeCellInput(' + r + "," + ci +
        ',this.value)" aria-label="' + escapeHtml(row.size + " " + c) + '"></td>'
      );
    }).join("");
    return (
      '<tr><td><input type="text" class="form-control form-control-sm fw-bold" maxlength="20" value="' +
      escapeHtml(row.size) + '" oninput="onSizeLabelInput(' + r + ',this.value)" aria-label="Size"></td>' +
      cells +
      '<td class="text-end"><button type="button" class="btn btn-sm text-danger p-0" ' +
      'onclick="removeSizeRow(' + r + ')" aria-label="Remove ' + escapeHtml(row.size) +
      '"><i class="bi bi-trash-fill"></i></button></td></tr>'
    );
  }).join("");

  host.innerHTML =
    '<div class="ap-st-wrap"><table class="ap-st-table"><thead><tr>' + head +
    "</tr></thead><tbody>" + body + "</tbody></table></div>";
}

function updateSizeSummary() {
  var box = document.getElementById("size_table_summary");
  var text = document.getElementById("size_table_summary_text");
  if (!box || !text) return;
  var chart = window.sizeChart;
  if (!chart) {
    box.classList.add("d-none");
    return;
  }
  var rows = chart.rows.length;
  var cols = chart.columns.length;
  text.textContent =
    "Size table added: " + rows + " size" + (rows === 1 ? "" : "s") + " · " +
    cols + " measurement" + (cols === 1 ? "" : "s");
  box.classList.remove("d-none");
}

function saveSizeTable() {
  var d = window.sizeDraft;
  var seen = {};
  var rows = [];
  d.rows.forEach(function (r) {
    var size = normalizeSize(r.size);
    if (!size || seen[size.toLowerCase()]) return;
    seen[size.toLowerCase()] = true;
    rows.push({
      size: size,
      values: d.columns.map(function (c, i) {
        return String(r.values[i] || "").trim().slice(0, 20);
      }),
    });
  });

  if (!d.columns.length && !rows.length) {
    window.sizeChart = null;
  } else if (!d.columns.length || !rows.length) {
    setSizeMsg("Add at least one measurement and one size, or use Clear table.");
    return;
  } else {
    window.sizeChart = { columns: d.columns.slice(), rows: rows };
  }

  updateSizeSummary();
  var modalEl = document.getElementById("sizeTableModal");
  var instance = modalEl && window.bootstrap ? bootstrap.Modal.getInstance(modalEl) : null;
  if (instance) instance.hide();
}

function clearSizeTable() {
  window.sizeDraft = { columns: [], rows: [] };
  setSizeMsg("Table cleared. Press Save size table to apply.");
  renderSizeTable();
}

function clearSavedSizeTable() {
  window.sizeChart = null;
  updateSizeSummary();
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

/* ===================== RESET / EDIT STATE ===================== */
function showEditingBanner(name) {
  var banner = document.getElementById("editing_banner");
  var label = document.getElementById("editing_name");
  if (label) label.textContent = name || "this item";
  if (banner) banner.classList.remove("d-none");
}

function hideEditingBanner() {
  var banner = document.getElementById("editing_banner");
  if (banner) banner.classList.add("d-none");
}

function resetProductFormState() {
  var form = document.getElementById("product_form");
  if (form) form.reset();

  window.selectedFiles = [];
  window.existingCover = null;
  window.productVariants = [];
  window.sizeChart = null;
  window.editingStagedId = null;

  document.querySelectorAll(".meetup-day").forEach(function (cb) { cb.checked = false; });

  var preview = document.getElementById("image_preview_container");
  if (preview) preview.innerHTML = coverEmptyHtml();
  var variantList = document.getElementById("variant_list");
  if (variantList) variantList.innerHTML = "";

  resetVariantForm();
  updateSizeSummary();
  hideEditingBanner();
  document.querySelectorAll(".staged-item.is-editing").forEach(function (el) {
    el.classList.remove("is-editing");
  });

  var categoryEl = document.getElementById("category");
  if (categoryEl) {
    categoryEl.value = "";
    if (typeof handleCategoryChange === "function") handleCategoryChange(categoryEl);
  }
}

function cancelEdit() {
  resetProductFormState();
  refreshNextProductCode();
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

  // A half-finished variation edit would be lost silently, so ask for it to be saved first
  if (isVariantMode && window.editingVariantIndex !== null) {
    return Swal.fire(
      "Save your variation first",
      "You're editing a variation. Press Save changes (or Cancel) before adding the product to the list.",
      "info",
    );
  }

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

  if (!validateMeetupDays(true)) {
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

  if (!validateMeetupTimeRange(true)) {
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

  // ---------- variations (or a single "Standard" variation for simple items) ----------
  let variants, finalPrice, finalStocks;
  if (isVariantMode) {
    if (!window.productVariants || window.productVariants.length === 0) {
      return Swal.fire("Variations Required", "Please add at least one variation.", "warning");
    }
    variants = window.productVariants;
    finalPrice = variants[0].price;
    finalStocks = variants.reduce((sum, v) => sum + (v.stock || 0), 0);
  } else {
    const price = parseFloat(priceEl && priceEl.value);
    const stock = parseInt(stocksEl && stocksEl.value, 10);
    if (!(price > 0)) {
      if (priceEl) { priceEl.classList.add("is-invalid"); priceEl.focus(); }
      return Swal.fire("Price Required", "Please enter a price greater than 0.", "warning");
    }
    if (Number.isNaN(stock) || stock < 0) {
      if (stocksEl) { stocksEl.classList.add("is-invalid"); stocksEl.focus(); }
      return Swal.fire("Stock Required", "Please enter how many items are available.", "warning");
    }
    variants = [{ name: "Standard", sizes: [], price: price, stock: stock, imageFile: null, keepFrom: null }];
    finalPrice = price;
    finalStocks = stock;
  }

  // ---------- cover photo ----------
  if (!window.selectedFiles.length && !window.existingCover) {
    return Swal.fire("Cover Photo Required", "Please add a cover photo.", "warning");
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

  formData.append(
    "variants",
    JSON.stringify(
      variants.map((v) => ({
        name: v.name,
        sizes: v.sizes || [],
        price: v.price,
        stock: v.stock,
        keepFrom: v.keepFrom || null,
      })),
    ),
  );
  variants.forEach((v, i) => {
    if (v.imageFile) formData.append("variant_image_" + i, v.imageFile);
  });

  if (window.selectedFiles[0]) {
    formData.append("cover", window.selectedFiles[0]);
  } else if (window.existingCover) {
    formData.append("keep_cover_id", window.existingCover.id);
  }

  if (window.sizeChart) formData.append("size_chart", JSON.stringify(window.sizeChart));
  if (window.editingStagedId) formData.append("editing_id", window.editingStagedId);

  // Approval letter
  const approvalInput = document.getElementById("approval_letter");
  if (approvalInput && approvalInput.files && approvalInput.files[0]) {
    formData.append("approval_letter", approvalInput.files[0]);
  }

  Swal.fire({
    title: "Saving to Staging...",
    allowOutsideClick: false,
    didOpen: () => Swal.showLoading(),
  });

  try {
    const response = await fetch("/api/staged-product/add/", {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken() },
      body: formData,
    });

    // Always read as text first so we never crash on HTML
    const raw = await response.text();
    let result;
    try {
      result = JSON.parse(raw);
    } catch (parseErr) {
      console.error("Non-JSON response from server:", raw.slice(0, 1000));
      Swal.fire(
        "Server Error",
        `Status ${response.status}. The server returned HTML instead of JSON.\n\nCheck the server log for the traceback.`,
        "error",
      );
      return;
    }

    if (result.status !== "success") {
      throw new Error(result.message || "Server error.");
    }

    const dbId = result.staged_id;
    const savedCode = result.product_code || productCode;

    // ----- Approval letter bookkeeping -----
    if (approvalInput && approvalInput.files && approvalInput.files[0]) {
      const reader = new FileReader();
      reader.onload = (e) => markApprovalLetterOnFile(e.target.result);
      reader.readAsDataURL(approvalInput.files[0]);
    } else if (result.approval_letter_saved) {
      window.approvalLetterOnFile = true;
    }

    // Build card image from the cover preview
    const firstImg = document.querySelector("#image_preview_container img");
    const imageHtml = firstImg
      ? `<img src="${escapeHtml(firstImg.src)}" alt="" class="rounded shadow-sm me-3" style="width:70px;height:70px;object-fit:cover;border:1px solid #dee2e6;">`
      : `<div class="bg-light rounded me-3 d-flex align-items-center justify-content-center" style="width:70px;height:70px;border:1px solid #dee2e6;"><i class="bi bi-image text-muted"></i></div>`;

    const daysLabel = selectedDays.join(", ");
    const timeLabel = `${fromInput.value} – ${toInput.value}`;
    const variantLabel = variants.length > 1 ? ` · ${variants.length} variations` : "";

    const itemCard = `
      <div class="card staged-item mb-3 p-3 bg-white border-0 shadow-sm animate__animated animate__fadeInRight" data-id="${dbId}">
        <div class="d-flex align-items-start mb-2">
          ${imageHtml}
          <div class="flex-grow-1">
            <div class="d-flex justify-content-between">
              <h6 class="mb-0 fw-bold text-dark">${escapeHtml(nameEl.value.trim())}</h6>
              <div class="d-flex flex-column gap-2">
                <button type="button" class="btn btn-sm text-danger p-0" onclick="removeItem(this, ${dbId})">
                  <i class="bi bi-trash-fill"></i>
                </button>
                <button type="button" class="btn btn-sm text-primary p-0" onclick="editItem(${dbId})">
                  <i class="bi bi-pencil-square"></i>
                </button>
              </div>
            </div>
            <div class="mt-1">
              <span class="badge bg-success-subtle text-success small">₱${Number(finalPrice).toFixed(2)}</span>
              <span class="text-muted small ms-1">Stock: ${finalStocks}${variantLabel}</span>
              ${isPreOrder ? `<span class="badge bg-primary-subtle text-primary small ms-1">Pre-order</span>` : ""}
            </div>
          </div>
        </div>
        <div class="small text-muted mb-2 text-truncate-2" style="font-size:0.85rem;">${escapeHtml(descEl?.value || "")}</div>
        <div class="d-flex flex-wrap gap-1 mb-2">
          ${savedCode ? `<span class="badge bg-dark text-white fw-normal"><i class="bi bi-upc me-1"></i>${escapeHtml(savedCode)}</span>` : ""}
          <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-tag me-1"></i>${escapeHtml(categoryName)}</span>
          <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-geo-alt me-1"></i>${escapeHtml(locationInput.value.trim())}</span>
          <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-calendar-week me-1"></i>${escapeHtml(daysLabel)}</span>
          <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-clock me-1"></i>${escapeHtml(timeLabel)}</span>
        </div>
      </div>`;

    // An edited item replaces its old card
    if (result.replaced_id) {
      const oldCard = document.querySelector(`.staged-item[data-id="${result.replaced_id}"]`);
      if (oldCard) oldCard.remove();
    }

    const stagingArea = document.getElementById("staging_area");
    if (stagingArea) {
      if (stagingArea.querySelector(".empty-msg")) stagingArea.innerHTML = "";
      stagingArea.insertAdjacentHTML("afterbegin", itemCard);
    }

    const countEl = document.getElementById("item_count");
    if (countEl) countEl.innerText = document.querySelectorAll(".staged-item").length;

    // Reset the form
    const nextCode = result.next_product_code || null;
    resetProductFormState();
    if (nextCode) setProductCodeValue(nextCode);
    else await refreshNextProductCode();

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

    // Start clean, then fill the form. The saved item stays in the list until you
    // press "Add to list" again (which replaces it), so cancelling loses nothing.
    resetProductFormState();
    window.editingStagedId = stagedId;

    const nameEl = document.getElementById("name");
    const descEl = document.getElementById("description");
    if (nameEl) nameEl.value = data.name || "";
    if (descEl) descEl.value = data.description || "";

    if (data.product_code) setProductCodeValue(data.product_code);

    const categorySelect = document.getElementById("category");
    if (categorySelect && data.category) {
      categorySelect.value = data.category;
      if (typeof handleCategoryChange === "function") {
        handleCategoryChange(categorySelect);
      }
    }

    const locationInput = document.getElementById("location_input");
    if (locationInput) locationInput.value = data.locations || "";

    const days = (data.available_days || "")
      .split(",")
      .map((d) => d.trim())
      .filter(Boolean);
    document.querySelectorAll(".meetup-day").forEach((cb) => {
      cb.checked = days.includes(cb.value);
    });

    const fromInput = document.getElementById("meetup_time_from");
    const toInput = document.getElementById("meetup_time_to");
    if (fromInput && data.meetup_time_from) fromInput.value = String(data.meetup_time_from).slice(0, 5);
    if (toInput && data.meetup_time_to) toInput.value = String(data.meetup_time_to).slice(0, 5);

    const preOrderEl = document.getElementById("is_pre_order");
    if (preOrderEl) preOrderEl.checked = !!data.pre_order;

    // ---------- cover ----------
    const images = data.images || [];
    const cover = images.find((i) => i.is_main) || images[0];
    if (cover) {
      window.existingCover = { id: cover.id, url: cover.url };
      renderCover(cover.url);
    }

    // ---------- variations ----------
    window.productVariants = (data.variants || []).map((v) => ({
      name: v.variant_name,
      sizes: splitSizes(v.attribute_value),
      price: Number(v.price),
      stock: Number(v.stocks),
      imageFile: null,
      imageUrl: v.image_url || null,
      keepFrom: v.id,
    }));
    renderVariantList();

    const vs = window.productVariants;
    const needsVariations = vs.length > 1 || vs.some((v) => v.sizes.length || v.imageUrl);
    if (needsVariations) {
      forceVariationMode();
    } else if (vs.length === 1) {
      const priceEl = document.getElementById("price");
      if (priceEl) priceEl.value = vs[0].price;
    }

    // ---------- size table ----------
    window.sizeChart = data.size_chart || null;
    updateSizeSummary();

    // ---------- banner + highlight ----------
    showEditingBanner(data.name);
    const card = document.querySelector(`.staged-item[data-id="${stagedId}"]`);
    if (card) card.classList.add("is-editing");

    document.getElementById("editing_banner")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  } catch (err) {
    console.error("Edit Error:", err);
    Swal.fire("Error", "Could not retrieve product data.", "error");
  }
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
  if (window.editingStagedId) {
    return Swal.fire(
      "Finish editing first",
      "Press Add to list to save your changes, or Cancel to discard them.",
      "info",
    );
  }

  const stagedCount = document.querySelectorAll(".staged-item").length;
  if (stagedCount === 0) {
    return Swal.fire({
      title: "Empty List",
      text: "Your staging list is empty! Add items first.",
      icon: "error",
      confirmButtonColor: "#198754",
    });
  }

  if (typeof validateApprovalLetter === "function" && !validateApprovalLetter()) {
    return Swal.fire(
      "Letter of Approval Required",
      "Please attach a Letter of Approval (JPG/PNG, max 10 MB).",
      "warning",
    );
  }

  const csrftoken = csrfToken();
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

  // Only send a new file if the user just selected one; otherwise backend uses the one already on file
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

/* ===================== REMOVE STAGED ITEM (asks first, then persists) ===================== */
async function removeItem(btn, productId) {
  const card = btn?.closest(".staged-item");
  const name = card?.querySelector("h6")?.textContent?.trim() || "this item";
  const beingEdited = String(window.editingStagedId) === String(productId);

  const answer = await Swal.fire({
    title: "Remove from staging?",
    html:
      `<strong>${escapeHtml(name)}</strong> will be removed from your staging list.` +
      (beingEdited
        ? "<br>You're editing it right now, so your unsaved changes will be discarded too."
        : "") +
      "<br>This can't be undone.",
    icon: "warning",
    showCancelButton: true,
    confirmButtonColor: "#dc3545",
    cancelButtonColor: "#6c757d",
    confirmButtonText: "Yes, remove it",
    cancelButtonText: "Keep it",
    focusCancel: true,
  });
  if (!answer.isConfirmed) return;

  // If this is the item being edited, drop the edit as well
  if (beingEdited) cancelEdit();

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
      headers: { "X-CSRFToken": csrfToken() },
    });
  } catch (err) {
    console.error("Failed to delete staged product on server:", err);
  }

  Swal.fire({
    toast: true,
    position: "top-end",
    icon: "success",
    title: "Removed from staging",
    showConfirmButton: false,
    timer: 1500,
  });
}

/* ===================== CATEGORY CHANGE ===================== */
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

  if (!selectedValue || selectedValue === "other") return;

  fetch(`/api/get-attributes/${selectedValue}/`)
    .then((response) => response.json())
    .then((data) => {
      // Limit to the 5 most recently used suggestions
      let attrs = data.attributes || [];
      if (attrs.length > 5) attrs = attrs.slice(0, 5);

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

            // A suggestion adds a size chip to the variation being built
            btn.onclick = function () {
              addSizeChip(attr.value);
              const sizeInput = document.getElementById("variant_size_input");
              if (sizeInput) sizeInput.focus();
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
          if (noAttributesNote) noAttributesNote.classList.remove("d-none");
        }
      }
    })
    .catch((err) => {
      console.error("Error fetching attributes:", err);
    });
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
             style="max-width:160px;max-height:120px;object-fit:contain"
             alt="Current Approval Letter">
      </a>
      <div class="small text-success fw-bold mt-1">
        <i class="bi bi-check-circle me-1"></i>Ready to upload
      </div>`;
  };
  reader.readAsDataURL(file);
}

function validateApprovalLetter() {
  const section = document.getElementById("approval_letter_section");
  if (!section) return true; // management / personal → skip

  // Already uploaded in this session OR was present on page load
  if (window.approvalLetterOnFile) return true;

  const input = document.getElementById("approval_letter");
  const hasFile = input && input.files && input.files.length > 0;
  const hasExistingImg = !!document.querySelector(
    '#approval_letter_section img[alt="Current Approval Letter"]',
  );

  if (hasFile || hasExistingImg) {
    return true;
  }

  const err = document.getElementById("approval_letter_error");
  if (err) {
    err.textContent = "Letter of Approval is required.";
    err.classList.remove("d-none");
  }
  return false;
}

/**
 * Call after a successful staged-product/add that included a letter.
 * Updates UI so the user no longer needs to re-select the file.
 */
function markApprovalLetterOnFile(previewUrl) {
  window.approvalLetterOnFile = true;

  const section = document.getElementById("approval_letter_section");
  if (!section) return;

  const preview = document.getElementById("approval_preview");
  if (preview) preview.innerHTML = "";

  const existingImg = section.querySelector('img[alt="Current Approval Letter"]');
  if (!existingImg && previewUrl) {
    const onFileHtml = `
      <div class="mb-2 d-flex align-items-start gap-3" id="approval_on_file_block">
        <a href="${previewUrl}" target="_blank" rel="noopener">
          <img src="${previewUrl}" alt="Current Approval Letter"
               class="rounded border shadow-sm"
               style="max-width:160px;max-height:120px;object-fit:contain;">
        </a>
        <div>
          <div class="small text-success fw-bold mb-1">
            <i class="bi bi-check-circle me-1"></i>Letter on file
          </div>
          <button type="button" class="btn btn-sm btn-outline-primary"
                  onclick="document.getElementById('approval_letter').click()">
            <i class="bi bi-arrow-repeat me-1"></i>Update
          </button>
        </div>
      </div>`;
    const errorEl = document.getElementById("approval_letter_error");
    if (errorEl) {
      errorEl.insertAdjacentHTML("beforebegin", onFileHtml);
    }
  }

  // Remove required so HTML5 validation doesn't block later
  const input = document.getElementById("approval_letter");
  if (input) {
    input.removeAttribute("required");
    input.value = ""; // clear the file input (letter is already on the server)
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

  // "Total stocks" only counts as required while it is editable (items without variants)
  const stocks = document.getElementById("stocks");
  const stockReq = document.getElementById("stock_required");
  const stockHint = document.getElementById("stock_hint");
  function syncStockLabel() {
    const editable = stocks && !stocks.readOnly;
    if (stockReq) stockReq.classList.toggle("d-none", !editable);
    if (stockHint) {
      stockHint.textContent = editable
        ? "How many items you have in total."
        : "Calculated automatically from your variations.";
    }
  }
  if (stocks) {
    new MutationObserver(syncStockLabel).observe(stocks, {
      attributes: true,
      attributeFilter: ["readonly"],
    });
    syncStockLabel();
  }

  // Size table dialog: load the working copy every time it opens
  const sizeModal = document.getElementById("sizeTableModal");
  if (sizeModal) sizeModal.addEventListener("show.bs.modal", initSizeDraft);

  const customColumn = document.getElementById("size_custom_column");
  if (customColumn) {
    customColumn.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); addCustomColumn(); }
    });
  }
  const newRow = document.getElementById("size_new_row");
  if (newRow) {
    newRow.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); addSizeRow(); }
    });
  }
});