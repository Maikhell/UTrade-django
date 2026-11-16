/* ===================================================================
   Product details: gallery, variation sheet, size guide, reviews
   =================================================================== */
(function () {
  "use strict";

  /* ---------- helpers ---------- */
  function byId(id) {
    return document.getElementById(id);
  }

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function money(n) {
    return (
      "\u20B1" +
      Number(n || 0).toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    );
  }

  function splitSizes(text) {
    var seen = {};
    var out = [];
    String(text || "")
      .split(",")
      .forEach(function (part) {
        var s = part.trim().replace(/\s+/g, " ");
        if (s && !seen[s.toLowerCase()]) {
          seen[s.toLowerCase()] = true;
          out.push(s);
        }
      });
    return out;
  }

  function csrf() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  function readJson(id) {
    var el = byId(id);
    if (!el) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.error("Could not read " + id + ":", e);
      return null;
    }
  }

  /* ---------- page data ---------- */
  var root = byId("pdRoot");
  var PRODUCT = {
    id: root ? root.dataset.productId : "",
    name: root ? root.dataset.productName : "",
    preOrder: root ? root.dataset.preOrder === "1" : false,
    totalStock: root ? parseInt(root.dataset.totalStock, 10) || 0 : 0,
    // pre-order: slots left across all variations (null = no limit)
    preorderLeft:
      root && root.dataset.preorderLeft !== "" && root.dataset.preorderLeft != null
        ? parseInt(root.dataset.preorderLeft, 10)
        : null,
    window: root ? root.dataset.preorderWindow || "" : "",
  };

  var variants = (readJson("variant-data") || []).map(function (v) {
    var remaining = v.remaining == null ? null : parseInt(v.remaining, 10);
    var unlimited = PRODUCT.preOrder && remaining === null;
    // "stock" here is how many can be added: pre-order slots left, or regular stock
    var available = PRODUCT.preOrder
      ? unlimited
        ? 99
        : Math.max(remaining || 0, 0)
      : parseInt(v.stock, 10) || 0;
    return {
      id: String(v.id),
      name: v.name || "",
      price: parseFloat(v.price) || 0,
      stock: available,
      unlimited: unlimited,
      sizes: splitSizes(v.attribute),
      image: (v.image_url || "").trim(),
      ownImage: !!v.own_image,
      condition: v.condition || "",
      flaws: v.flaws || "",
    };
  });
  var sizeChart = readJson("size-chart-data");
  if (!sizeChart || !sizeChart.columns || !sizeChart.rows) sizeChart = null;

  var state = { isPreOrder: false, variantId: null, size: "", qty: 1 };
  var pagePreviewId = null;

  function variantById(id) {
    for (var i = 0; i < variants.length; i++) {
      if (variants[i].id === String(id)) return variants[i];
    }
    return null;
  }

  function selectedVariant() {
    return state.variantId ? variantById(state.variantId) : null;
  }

  function slotsText(v) {
    if (!PRODUCT.preOrder) return "";
    return v.unlimited ? "No limit" : v.stock + " left";
  }

  /* ---------- wishlist ---------- */
  async function toggleWishlist(productId, buttonElement, isWishlistPage) {
    if (!buttonElement || typeof buttonElement.querySelector !== "function") return;
    var icon = buttonElement.querySelector("i");

    try {
      var response = await fetch("/wishlist/toggle/" + productId + "/", {
        method: "POST",
        headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" },
      });
      var data = await response.json();

      if (data.status === "success") {
        if (data.action === "added") {
          icon.classList.replace("bi-heart", "bi-heart-fill");
          Swal.fire({ toast: true, position: "top-end", icon: "success", title: "Added to Wishlist", showConfirmButton: false, timer: 1500 });
        } else {
          icon.classList.replace("bi-heart-fill", "bi-heart");
          if (isWishlistPage) {
            var card = byId("wishlist-item-" + productId);
            if (card) {
              card.style.transition = "0.3s";
              card.style.opacity = "0";
              card.style.transform = "scale(0.9)";
              setTimeout(function () { card.remove(); }, 300);
            }
          }
          Swal.fire({ toast: true, position: "top-end", icon: "info", title: "Removed from Wishlist", showConfirmButton: false, timer: 1500 });
        }
      }
    } catch (e) {
      Swal.fire("Oops!", "Something went wrong. Are you logged in?", "error");
    }
  }

  /* ---------- lightbox (works above the sheet too) ---------- */
  function openLightbox(src) {
    if (!src) return;
    Swal.fire({
      imageUrl: src,
      imageAlt: "Photo",
      showConfirmButton: false,
      showCloseButton: true,
      width: "auto",
      padding: "1rem",
      customClass: { image: "pd-lightbox-img" },
    });
  }

  /* ---------- gallery ---------- */
  function setMainImage(url) {
    var img = byId("mainDisplayImage");
    if (!img || !url || img.getAttribute("src") === url) return;
    img.style.opacity = "0";
    setTimeout(function () {
      img.src = url;
      img.style.opacity = "1";
    }, 150);
  }

  function markThumb(url, element) {
    var thumbs = document.querySelectorAll("#thumbGallery .pd-thumb");
    thumbs.forEach(function (t) {
      t.classList.toggle("active", element ? t === element : t.dataset.src === url);
    });
  }

  function changeImage(url, element) {
    setMainImage(url);
    markThumb(url, element || null);
    var match = variants.filter(function (v) {
      return v.ownImage && v.image === url;
    })[0];
    if (match) previewVariant(match.id, true);
  }

  /* ---------- page: variation strip, sizes, price preview ---------- */
  function previewVariant(id, fromImage) {
    var v = variantById(id);
    if (!v) return;
    pagePreviewId = v.id;
    var price = byId("displayPrice");
    if (price) price.textContent = money(v.price);
    if (!fromImage && v.image) {
      setMainImage(v.image);
      markThumb(v.image, null);
    }
    renderStrip();
  }

  function renderStrip() {
    var wrap = byId("pdVariationWrap");
    var strip = byId("pdVariationStrip");
    if (!wrap || !strip) return;
    if (variants.length < 2) {
      wrap.hidden = true;
      return;
    }
    wrap.hidden = false;
    strip.innerHTML = variants
      .map(function (v) {
        var cls = "pd-chip" + (pagePreviewId === v.id ? " is-selected" : "") + (v.stock <= 0 ? " is-soldout" : "");
        return (
          '<button type="button" class="' + cls + '" data-variant="' + esc(v.id) + '">' +
          (v.image ? '<img src="' + esc(v.image) + '" alt="">' : "") +
          "<span>" + esc(v.name) + "</span>" +
          (PRODUCT.preOrder ? "<small>" + esc(v.stock <= 0 ? "Fully booked" : slotsText(v)) + "</small>" : "") +
          "</button>"
        );
      })
      .join("");
  }

  function renderPageSizes() {
    var line = byId("pdSizesLine");
    var list = byId("pdSizesList");
    if (!line || !list) return;
    var seen = {};
    var all = [];
    variants.forEach(function (v) {
      v.sizes.forEach(function (s) {
        if (!seen[s.toLowerCase()]) {
          seen[s.toLowerCase()] = true;
          all.push(s);
        }
      });
    });
    if (!all.length) {
      line.hidden = true;
      return;
    }
    line.hidden = false;
    list.innerHTML = all
      .map(function (s) {
        return '<span class="pd-size-pill">' + esc(s) + "</span>";
      })
      .join("");
    var guide = byId("pdSizeGuideLink");
    if (guide) guide.hidden = !sizeChart;
  }

  /* ---------- size guide ---------- */
  function sizeGuideHtml(activeSize) {
    if (!sizeChart) return "";
    var head =
      "<th>Size</th>" +
      sizeChart.columns.map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("");
    var body = sizeChart.rows
      .map(function (row) {
        var active = activeSize && String(row.size).toLowerCase() === String(activeSize).toLowerCase();
        return (
          '<tr class="' + (active ? "is-active" : "") + '"><th scope="row">' + esc(row.size) + "</th>" +
          sizeChart.columns
            .map(function (c, i) { return "<td>" + esc((row.values || [])[i] || "—") + "</td>"; })
            .join("") +
          "</tr>"
        );
      })
      .join("");
    return (
      '<div class="pd-guide-wrap"><table class="pd-guide"><thead><tr>' + head +
      "</tr></thead><tbody>" + body + "</tbody></table></div>" +
      '<p class="pd-guide-note">Measurements are provided by the seller and may vary slightly.</p>'
    );
  }

  function openSizeGuide() {
    if (!sizeChart) return;
    byId("pdSizeGuideBody").innerHTML = sizeGuideHtml(state.size);
    bootstrap.Modal.getOrCreateInstance(byId("pdSizeGuide")).show();
  }

  function toggleInlineGuide() {
    var box = byId("sheetGuide");
    if (!box || !sizeChart) return;
    if (box.classList.contains("d-none")) {
      box.innerHTML = sizeGuideHtml(state.size);
      box.classList.remove("d-none");
    } else {
      box.classList.add("d-none");
    }
  }

  /* ---------- variation sheet ---------- */
  function isValid() {
    var v = selectedVariant();
    if (!v || v.stock <= 0) return false;
    if (v.sizes.length && !state.size) return false;
    return state.qty >= 1 && state.qty <= v.stock;
  }

  function hintText() {
    var v = selectedVariant();
    if (!v) return "Please select a variation.";
    if (v.sizes.length && !state.size) return "Please select a size.";
    return "";
  }

  function stockLine(v) {
    if (PRODUCT.preOrder) {
      if (v) return v.unlimited ? "No pre-order limit" : "Pre-order slots left: " + v.stock;
      return PRODUCT.preorderLeft === null ? "No pre-order limit" : "Pre-order slots left: " + PRODUCT.preorderLeft;
    }
    return "Stock: " + (v ? v.stock : PRODUCT.totalStock);
  }

  function renderHeader() {
    var v = selectedVariant();
    var main = byId("mainDisplayImage");
    var src = (v && v.image) || (main ? main.src : "");
    var thumb = byId("sheetThumb");
    if (thumb) {
      if (src) {
        thumb.src = src;
        thumb.classList.remove("d-none");
      } else {
        thumb.classList.add("d-none");
      }
    }
    var page = byId("displayPrice");
    byId("sheetPrice").textContent = v ? money(v.price) : page ? page.textContent : "";
    byId("sheetStock").textContent = stockLine(v);

    var bits = [];
    if (v && variants.length > 1) bits.push(v.name);
    if (state.size) bits.push(state.size);
    byId("sheetSelected").textContent = bits.length ? "Selected: " + bits.join(" · ") : "";

    // Notes: pre-order period, and a condition only when it matters (older listings)
    var note = byId("sheetNote");
    var lines = [];
    if (PRODUCT.preOrder && PRODUCT.window) lines.push("Pre-order period: " + PRODUCT.window);
    if (v && v.condition && v.condition.toLowerCase() !== "brand new") lines.push("Condition: " + v.condition);
    if (v && v.flaws) lines.push("Notes: " + v.flaws);
    if (lines.length) {
      note.innerHTML = lines.map(esc).join("<br>");
      note.classList.remove("d-none");
    } else {
      note.classList.add("d-none");
    }
  }

  function renderVariantChips() {
    var block = byId("sheetVariantBlock");
    var box = byId("sheetVariantChips");
    if (variants.length < 2) {
      block.classList.add("d-none");
      return;
    }
    block.classList.remove("d-none");
    box.innerHTML = variants
      .map(function (v) {
        var out = v.stock <= 0;
        var cls = "pd-chip" + (state.variantId === v.id ? " is-selected" : "") + (out ? " is-disabled" : "");
        var label = out ? (PRODUCT.preOrder ? " · Fully booked" : " · Sold out") : "";
        return (
          '<button type="button" class="' + cls + '" data-variant="' + esc(v.id) + '"' + (out ? " disabled" : "") + ">" +
          (v.image ? '<img src="' + esc(v.image) + '" alt="">' : "") +
          "<span>" + esc(v.name) + label + "</span>" +
          (PRODUCT.preOrder && !out ? "<small>" + esc(slotsText(v)) + "</small>" : "") +
          "</button>"
        );
      })
      .join("");
  }

  function renderSizeChips() {
    var v = selectedVariant();
    var block = byId("sheetSizeBlock");
    if (!v || !v.sizes.length) {
      block.classList.add("d-none");
      return;
    }
    block.classList.remove("d-none");
    byId("sheetSizeChips").innerHTML = v.sizes
      .map(function (s) {
        var on = state.size === s;
        return '<button type="button" class="pd-size' + (on ? " is-selected" : "") + '" data-size="' + esc(s) + '">' + esc(s) + "</button>";
      })
      .join("");
    var guideBtn = byId("sheetSizeGuideBtn");
    if (guideBtn) guideBtn.hidden = !sizeChart;
    var guide = byId("sheetGuide");
    if (guide && !guide.classList.contains("d-none")) guide.innerHTML = sizeGuideHtml(state.size);
  }

  function renderQty() {
    var v = selectedVariant();
    var input = byId("sheetQty");
    var max = v ? Math.max(v.stock, 1) : 99;
    input.max = max;
    input.value = state.qty;
    byId("sheetQtyMinus").disabled = state.qty <= 1;
    byId("sheetQtyPlus").disabled = state.qty >= max;
  }

  function renderFooter() {
    var v = selectedVariant();
    byId("sheetTotal").textContent = v ? money(v.price * state.qty) : "\u2014";
    var btn = byId("sheetConfirm");
    btn.disabled = !isValid();
    btn.textContent = state.isPreOrder ? "Add Pre-order to Cart" : "Add to Cart";
    btn.classList.toggle("btn-primary", state.isPreOrder);
    btn.classList.toggle("btn-success", !state.isPreOrder);
    byId("sheetHint").textContent = hintText();
  }

  function renderSheet() {
    renderHeader();
    renderVariantChips();
    renderSizeChips();
    renderQty();
    renderFooter();
  }

  function selectVariant(id) {
    var v = variantById(id);
    if (!v || v.stock <= 0) return;
    state.variantId = v.id;
    state.size = v.sizes.length === 1 ? v.sizes[0] : "";
    state.qty = Math.min(Math.max(1, state.qty), v.stock);
    previewVariant(v.id); // keeps the page price and photo in step
    renderSheet();
  }

  function selectSize(size) {
    state.size = size;
    renderSizeChips();
    renderHeader();
    renderFooter();
  }

  function setQty(n) {
    var v = selectedVariant();
    var max = v ? Math.max(v.stock, 1) : 99;
    state.qty = Math.min(Math.max(1, n || 1), max);
    renderQty();
    renderFooter();
  }

  function openVariantSelector(productId, productName, isPreOrder, presetVariantId) {
    // Older listings without any variation rows
    if (!variants.length) {
      performAddToCart([{ variant_id: productId, quantity: 1 }], !!isPreOrder);
      return;
    }

    state.isPreOrder = !!isPreOrder;
    state.variantId = null;
    state.size = "";
    state.qty = 1;
    var guide = byId("sheetGuide");
    if (guide) guide.classList.add("d-none");

    var preset = presetVariantId || pagePreviewId;
    var presetVariant = preset ? variantById(preset) : null;
    if (presetVariant && presetVariant.stock > 0) {
      selectVariant(presetVariant.id);
    } else if (variants.length === 1 && variants[0].stock > 0) {
      selectVariant(variants[0].id);
    }

    var pickup = byId("pdPickupText");
    byId("sheetPickup").textContent = pickup ? pickup.textContent.replace(/\s+/g, " ").trim() : "";

    renderSheet();
    bootstrap.Modal.getOrCreateInstance(byId("variantSheet")).show();
  }

  function confirmSelection() {
    var v = selectedVariant();
    if (!v || !isValid()) {
      renderFooter();
      return;
    }
    var payload = [{ variant_id: v.id, quantity: state.qty, size: state.size }];
    var modal = bootstrap.Modal.getInstance(byId("variantSheet"));
    if (modal) modal.hide();
    // Pre-orders are added to the cart too; the seller gets them when the buyer checks out
    performAddToCart(payload, state.isPreOrder);
  }

  /* ---------- requests ---------- */
  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrf(),
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify(body),
    }).then(function (r) {
      return r.json();
    });
  }

  function performAddToCart(items, isPreOrder) {
    postJson("/cart/add-batch/", { items: items })
      .then(function (data) {
        if (data.success) {
          var badge = byId("cart-count");
          if (badge) {
            badge.innerText = data.cart_count;
            badge.style.display = "inline-block";
          }
          Swal.fire({
            icon: "success",
            title: isPreOrder ? "Pre-order added to cart!" : "Added to Cart!",
            text: isPreOrder ? "Check out from your cart to place the pre-order." : undefined,
            timer: isPreOrder ? 2600 : 1500,
            showConfirmButton: false,
          });
        } else {
          Swal.fire({ icon: "error", title: "Error", text: data.message });
        }
      })
      .catch(function () {
        Swal.fire("Error", "Login required or network failure.", "error");
      });
  }

  // Kept for older callers: pre-orders now go through the cart.
  function performPreOrderRequest(items) {
    performAddToCart(items, true);
  }

  function addToCart(productId) {
    fetch("/cart/add/" + productId + "/", {
      method: "POST",
      headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          var badge = byId("cart-count");
          if (badge) {
            badge.innerText = data.cart_count;
            badge.style.display = "inline-block";
          }
          Swal.fire({ toast: true, position: "top-end", icon: "success", title: "Added to Cart", timer: 1500, showConfirmButton: false });
        } else {
          Swal.fire({ icon: "error", title: "Error", text: data.message });
        }
      })
      .catch(function () {
        Swal.fire("Login Required", "", "warning");
      });
  }

  function addToCartWithVariant(productId) {
    var h1 = document.querySelector("h1");
    openVariantSelector(productId, h1 ? h1.innerText : "Product", PRODUCT.preOrder);
  }

  function showLoginPrompt() {
    var loginUrl = byId("login-url") ? byId("login-url").value : "";
    Swal.fire({
      title: "Login Required",
      text: "You need to log in first.",
      icon: "info",
      showCancelButton: true,
      confirmButtonText: "Login",
    }).then(function (r) {
      if (r.isConfirmed && loginUrl) window.location.href = loginUrl;
    });
  }

  function showVerificationModal() {
    var statusEl = byId("user-verification-status");
    if (!statusEl) return;
    var status = statusEl.value;
    if (status === "unverified" || status === "Pending") {
      var modalEl = byId("verificationModal");
      if (modalEl) new bootstrap.Modal(modalEl).show();
    }
  }

  /* ---------- reviews ---------- */
  function initReviewFilters() {
    var chips = document.querySelectorAll("[data-rv-filter]");
    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        chips.forEach(function (c) { c.classList.remove("active"); });
        chip.classList.add("active");
        var f = chip.dataset.rvFilter;
        var shown = 0;
        document.querySelectorAll(".pd-review").forEach(function (rv) {
          var ok = f === "all" || (f === "media" ? rv.dataset.media === "1" : rv.dataset.rating === f);
          rv.hidden = !ok;
          if (ok) shown++;
        });
        var empty = byId("pdReviewsEmpty");
        if (empty) empty.hidden = shown !== 0;
      });
    });
  }

  /* ---------- wiring ---------- */
  function init() {
    renderStrip();
    renderPageSizes();
    initReviewFilters();

    var strip = byId("pdVariationStrip");
    if (strip) {
      strip.addEventListener("click", function (e) {
        var chip = e.target.closest("[data-variant]");
        if (chip) previewVariant(chip.dataset.variant);
      });
    }

    var pageGuide = byId("pdSizeGuideLink");
    if (pageGuide) pageGuide.addEventListener("click", openSizeGuide);

    var sheet = byId("variantSheet");
    if (!sheet) return;

    sheet.addEventListener("click", function (e) {
      var chip = e.target.closest("[data-variant]");
      if (chip && !chip.disabled) {
        selectVariant(chip.dataset.variant);
        return;
      }
      var size = e.target.closest("[data-size]");
      if (size) selectSize(size.dataset.size);
    });

    byId("sheetQtyMinus").addEventListener("click", function () { setQty(state.qty - 1); });
    byId("sheetQtyPlus").addEventListener("click", function () { setQty(state.qty + 1); });
    byId("sheetQty").addEventListener("change", function (e) { setQty(parseInt(e.target.value, 10)); });
    byId("sheetConfirm").addEventListener("click", confirmSelection);
    byId("sheetSizeGuideBtn").addEventListener("click", toggleInlineGuide);
    byId("sheetThumbBtn").addEventListener("click", function () {
      var img = byId("sheetThumb");
      if (img && img.src) openLightbox(img.src);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  /* ---------- public functions used by inline onclick handlers ---------- */
  window.toggleWishlist = toggleWishlist;
  window.openLightbox = openLightbox;
  window.changeImage = changeImage;
  window.openVariantSelector = openVariantSelector;
  window.openSizeGuide = openSizeGuide;
  window.performAddToCart = performAddToCart;
  window.performPreOrderRequest = performPreOrderRequest;
  window.addToCart = addToCart;
  window.addToCartWithVariant = addToCartWithVariant;
  window.showLoginPrompt = showLoginPrompt;
  window.showVerificationModal = showVerificationModal;
})();