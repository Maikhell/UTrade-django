let serviceCount = 0;
let currentAttributes = { sizes: [], varieties: [], colors: [] };
function previewMultipleImages(event) {
    const container = document.getElementById('image_preview_container');
    container.innerHTML = ''; 
    const files = event.target.files;
    if (files) {
        Array.from(files).forEach((file) => {
            const reader = new FileReader();
            reader.onload = function (e) {
                const img = document.createElement('img');
                img.src = e.target.result;
                img.className = 'preview-box shadow-sm';
                container.appendChild(img);
            }
            reader.readAsDataURL(file);
        });
    }
}
function addTag(type) {
    const input = document.getElementById(`${type}_input`);
    const tagContainer = document.getElementById(`${type}_tags`); 
    const mainDisplay = document.getElementById('attribute_pills'); 
    const val = input.value.trim();

    if (!val) return;

    if (!currentAttributes[`${type}s`].includes(val)) {
        currentAttributes[`${type}s`].push(val);
        const pillHtml = `
            <span class="badge rounded-pill bg-light text-dark border p-2 me-1 mb-1 animate__animated animate__fadeIn">
                ${val} <i class="bi bi-x-circle-fill ms-1 text-danger cursor-pointer" onclick="removeTag('${type}', '${val}', this)"></i>
            </span>`;
        
        mainDisplay.insertAdjacentHTML('beforeend', pillHtml);
        tagContainer.insertAdjacentHTML('beforeend', pillHtml);
    }
    input.value = '';
}

function removeTag(type, val, element) {
    currentAttributes[`${type}s`] = currentAttributes[`${type}s`].filter(item => item !== val);
    element.parentElement.remove();
}
function addToStaging() {
    const name = document.getElementById('name').value;
    const price = document.getElementById('price').value;
    const slots = document.getElementById('stocks').value; 
    const desc = document.getElementById('description').value;
    
    const categoryEl = document.getElementById('category');
    const categoryName = categoryEl.options[categoryEl.selectedIndex].text;
    
    const delivery = document.getElementById('condition').value; 
    const leadTime = document.getElementById('meetup').value;    

    const paymentEl = document.querySelector('input[name="payment"]:checked');
    const payment = paymentEl ? paymentEl.value : 'Not Specified';

    const stagingArea = document.getElementById('staging_area');

    if (!name || !price || !slots) return alert('Please fill in Service Title, Price, and Slots!');

    serviceCount++;
    document.getElementById('item_count').innerText = serviceCount;
    if (stagingArea.querySelector('.empty-msg')) stagingArea.innerHTML = '';
    const attrBadges = [
        ...currentAttributes.sizes.map(s => `<span class="badge bg-primary-subtle text-primary me-1 border border-primary-subtle">${s}</span>`),
        ...currentAttributes.varieties.map(v => `<span class="badge bg-info-subtle text-info me-1 border border-info-subtle">${v}</span>`),
        ...currentAttributes.colors.map(c => `<span class="badge bg-dark-subtle text-dark me-1 border">${c}</span>`)
    ].join('');

    const serviceCard = `
        <div class="card staged-item mb-3 p-3 bg-white border-0 shadow-sm animate__animated animate__fadeInRight" style="border-left: 5px solid #0d6efd !important;">
            <div class="d-flex justify-content-between align-items-start mb-2">
                <div>
                    <h6 class="mb-0 fw-bold text-dark">${name}</h6>
                    <span class="badge bg-primary-subtle text-primary small">Starts ₱${price}</span>
                    <span class="text-muted small ms-1">Slots: ${slots}</span>
                </div>
                <button class="btn btn-sm text-danger p-0" onclick="removeItem(this)">
                    <i class="bi bi-trash-fill"></i>
                </button>
            </div>

            <div class="small text-muted mb-2 text-truncate-2" style="font-size: 0.85rem;">
                ${desc}
            </div>

            <div class="d-flex flex-wrap gap-1 mb-2">
                <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-layers me-1"></i>${categoryName}</span>
                <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-truck me-1"></i>${delivery}</span>
                <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-clock me-1"></i>${leadTime}</span>
                <span class="badge ${payment === 'GCash' ? 'bg-primary' : 'bg-success'} text-white fw-normal">
                    <i class="bi bi-wallet2 me-1"></i>${payment}
                </span>
            </div>

            <div class="pt-2 border-top">
                ${attrBadges ? attrBadges : '<span class="text-muted tiny" style="font-size: 0.7rem;">Standard Service</span>'}
            </div>
        </div>`;

    stagingArea.insertAdjacentHTML('afterbegin', serviceCard);
    document.getElementById('product_form').reset();
    currentAttributes = { sizes: [], varieties: [], colors: [] }; 
    document.getElementById('attribute_pills').innerHTML = ''; 
    document.getElementById('size_tags').innerHTML = '';
    document.getElementById('variety_tags').innerHTML = '';
    document.getElementById('color_tags').innerHTML = '';
    document.getElementById('image_preview_container').innerHTML = `
        <div class="text-center py-5 text-muted small w-100">
            <i class="bi bi-stars text-primary d-block mb-2"></i>
            Service added. Ready for next.
        </div>`;
}

function removeItem(btn) {
    btn.closest('.staged-item').remove();
    serviceCount--;
    document.getElementById('item_count').innerText = serviceCount;
    if(serviceCount === 0) {
        document.getElementById('staging_area').innerHTML = '<div class="text-center py-5 text-muted small empty-msg">No services staged.</div>';
    }
}