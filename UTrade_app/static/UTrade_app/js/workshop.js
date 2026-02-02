    let itemCount = 0;
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
                    img.className = 'preview-box';
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
                <span class="badge rounded-pill bg-light text-dark border p-2 me-1 mb-1">
                    ${val} <i class="bi bi-x-circle-fill ms-1 text-danger cursor-pointer" onclick="removeTag('${type}', '${val}', this)"></i>
                </span>`;
            
            mainDisplay.insertAdjacentHTML('beforeend', pillHtml);
            tagContainer.insertAdjacentHTML('beforeend', pillHtml);
        }
        input.value = '';
    }
function addToStaging() {
    const name = document.getElementById('name').value;
    const price = document.getElementById('price').value;
    const stocks = document.getElementById('stocks').value;
    const desc = document.getElementById('description').value;
    const categoryEl = document.getElementById('category');
    const categoryName = categoryEl.options[categoryEl.selectedIndex].text;
    
    const condition = document.getElementById('condition').value;
    const meetup = document.getElementById('meetup').value;

    const paymentEl = document.querySelector('input[name="payment"]:checked');
    const payment = paymentEl ? paymentEl.value : 'Not Specified';

    const stagingArea = document.getElementById('staging_area');

    if (!name || !price || !stocks) return alert('Please fill in Name, Price, and Stocks!');

    itemCount++;
    document.getElementById('item_count').innerText = itemCount;
    if (stagingArea.querySelector('.empty-msg')) stagingArea.innerHTML = '';

    const attrBadges = [
        ...currentAttributes.sizes.map(s => `<span class="badge bg-secondary-subtle text-dark me-1 border">${s}</span>`),
        ...currentAttributes.varieties.map(v => `<span class="badge bg-info-subtle text-dark me-1 border">${v}</span>`),
        ...currentAttributes.colors.map(c => `<span class="badge bg-dark-subtle text-dark me-1 border">${c}</span>`)
    ].join('');
    const itemCard = `
        <div class="card staged-item mb-3 p-3 bg-white border-0 shadow-sm animate__animated animate__fadeInRight">
            <div class="d-flex justify-content-between align-items-start mb-2">
                <div>
                    <h6 class="mb-0 fw-bold text-dark">${name}</h6>
                    <span class="badge bg-success-subtle text-success small">₱${price}</span>
                    <span class="text-muted small ms-1">Stock: ${stocks}</span>
                </div>
                <button class="btn btn-sm text-danger p-0" onclick="removeItem(this)">
                    <i class="bi bi-trash-fill"></i>
                </button>
            </div>

            <div class="small text-muted mb-2 text-truncate-2" style="font-size: 0.85rem;">
                ${desc}
            </div>

            <div class="d-flex flex-wrap gap-1 mb-2">
                <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-tag me-1"></i>${categoryName}</span>
                <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-star me-1"></i>${condition}</span>
                <span class="badge bg-light text-dark border fw-normal"><i class="bi bi-geo-alt me-1"></i>${meetup}</span>
                <span class="badge ${payment === 'GCash' ? 'bg-primary' : 'bg-success'} text-white fw-normal">
                    <i class="bi bi-wallet2 me-1"></i>${payment}
                </span>
            </div>

            <div class="pt-2 border-top">
                ${attrBadges ? attrBadges : '<span class="text-muted tiny" style="font-size: 0.7rem;">No specific attributes</span>'}
            </div>
        </div>`;
    stagingArea.insertAdjacentHTML('afterbegin', itemCard);
    document.getElementById('product_form').reset();
    currentAttributes = { sizes: [], varieties: [], colors: [] }; 
    document.getElementById('attribute_pills').innerHTML = ''; 
    document.getElementById('size_tags').innerHTML = '';
    document.getElementById('variety_tags').innerHTML = '';
    document.getElementById('color_tags').innerHTML = '';
    document.getElementById('image_preview_container').innerHTML = `
        <div class="text-center py-5 text-muted small w-100">
            <i class="bi bi-check-circle-fill text-success d-block mb-2"></i>
            Item added. Ready for next.
        </div>`;
}
function removeItem(btn) {
    btn.closest('.staged-item').remove();
    itemCount--;
    document.getElementById('item_count').innerText = itemCount;
    if(itemCount === 0) {
        document.getElementById('staging_area').innerHTML = '<div class="text-center py-5 text-muted small empty-msg">List is empty.</div>';
    }
}
