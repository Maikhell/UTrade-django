/**
 * Unified Delete Function using SweetAlert2
 */
async function confirmDelete(id, type, url) {
    const result = await Swal.fire({
        title: 'Are you sure?',
        text: `You are about to delete this ${type}. This action cannot be undone.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Yes, delete it!',
        cancelButtonText: 'Cancel'
    });

    if (result.isConfirmed) {
        try {
            const formData = new FormData();
            // Fallback for CSRF token if not in a hidden input
            const csrf = document.getElementById('csrf_token')?.value || document.querySelector('[name=csrfmiddlewaretoken]')?.value;
            formData.append('csrfmiddlewaretoken', csrf);

            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            const data = await response.json();

            if (data.status === 'success') {
                Swal.fire('Deleted!', `The ${type} has been removed.`, 'success');
                const elementId = `${type}-${id}`;
                const element = document.getElementById(elementId);
                
                if (element) {
                    element.classList.add('animate__animated', 'animate__fadeOut');
                    setTimeout(() => element.remove(), 500);
                } else {
                    location.reload(); 
                }
            } else {
                Swal.fire('Error!', data.message, 'error');
            }
        } catch (error) {
            Swal.fire('Error!', 'A system error occurred while deleting.', 'error');
            console.error(error);
        }
    }
}

// Wrapper functions - UPDATED WITH /management/security/ PREFIX
function deleteBadWord(wordId) {
    confirmDelete(wordId, 'word', `/management/security/delete-word/${wordId}/`);
}

function deleteMeetup(locId) {
    confirmDelete(locId, 'meetup', `/management/security/delete-meetup/${locId}/`);
}

function deleteCategory(catId) {
    confirmDelete(catId, 'category', `/management/security/categories/delete/${catId}/`);
}

/** * ADD FUNCTIONS 
 */

function submitBadWord() {
    const input = document.getElementById('new_bad_word');
    const word = input.value.trim();
    if (!word) return;

    const btn = document.getElementById('btn-add-word');
    const url = btn.getAttribute('data-url');
    const csrf = document.getElementById('csrf_token')?.value || document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    const formData = new FormData();
    formData.append('word', word);
    formData.append('csrfmiddlewaretoken', csrf);

    fetch(url, { method: 'POST', body: formData })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const container = document.getElementById('bad_words_container');
                const newBadge = `
                <div class="badge-wrapper animate__animated animate__zoomIn" id="word-${data.id}">
                    <span class="badge bg-light text-dark border p-2 d-flex align-items-center gap-2">
                        ${data.word}
                        <i class="bi bi-x-circle-fill text-danger cursor-pointer" onclick="deleteBadWord(${data.id})"></i>
                    </span>
                </div>`;
                container.insertAdjacentHTML('afterbegin', newBadge);
                input.value = '';
            } else {
                Swal.fire('Error', data.message, 'error');
            }
        });
}

function submitMeetup() {
    const input = document.getElementById('new_meetup_input');
    const locationValue = input.value.trim();
    if (!locationValue) return;

    const url = document.getElementById('btn-add-meetup').getAttribute('data-url');
    const csrf = document.getElementById('csrf_token')?.value || document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    const formData = new FormData();
    formData.append('location', locationValue);
    formData.append('csrfmiddlewaretoken', csrf);

    fetch(url, { method: 'POST', body: formData })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                const container = document.getElementById('meetups_container');
                const html = `
                <div class="col-md-4 mb-2 animate__animated animate__fadeInUp" id="meetup-${data.id}">
                    <div class="p-3 border rounded d-flex justify-content-between align-items-center bg-light">
                        <span class="fw-bold">${data.location}</span>
                        <button class="btn btn-sm text-danger" onclick="deleteMeetup(${data.id})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>`;
                container.insertAdjacentHTML('beforeend', html);
                input.value = '';
            } else {
                Swal.fire('Error', data.message, 'error');
            }
        });
}

function submitCategory() {
    const input = document.getElementById('new_category_input');
    const name = input.value.trim();
    if (!name) return;

    const url = document.getElementById('btn-add-category').getAttribute('data-url');
    const csrf = document.getElementById('csrf_token')?.value || document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    const formData = new FormData();
    formData.append('name', name);
    formData.append('csrfmiddlewaretoken', csrf);

    fetch(url, { method: 'POST', body: formData })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                const container = document.getElementById('categories_table_body');
                const html = `
                <tr class="animate__animated animate__fadeInDown" id="category-${data.id}">
                    <td class="fw-bold">${data.name}</td>
                    <td><code class="small text-muted">New</code></td>
                    <td class="text-end">
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteCategory(${data.id})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>
                </tr>`;
                container.insertAdjacentHTML('afterbegin', html);
                input.value = '';
            } else {
                Swal.fire('Error', data.message, 'error');
            }
        });
}
function addAttributeRow() {
    const container = document.getElementById('attribute_fields_container');
    const newRow = document.createElement('div');
    newRow.className = 'input-group mb-2 attribute-row';
    newRow.innerHTML = `
        <select class="form-select attr-type">
            <option value="size">Size</option>
            <option value="color">Color</option>
            <option value="volume">Volume/Weight</option>
            <option value="quantity">Quantity Unit</option>
            <option value="other">Other</option>
        </select>
        <input type="text" class="form-control attr-value" placeholder="Value">
        <button class="btn btn-outline-danger" type="button" onclick="this.parentElement.remove()"><i class="bi bi-trash"></i></button>
    `;
    container.appendChild(newRow);
}

// Function to collect all data and send to Django
async function submitCategoryWithAttributes() {
    const categoryName = document.getElementById('new_category_input').value;
    const url = document.getElementById('btn-add-category').getAttribute('data-url');
    const csrfToken = document.getElementById('csrf_token').value;

    if (!categoryName) {
        return Swal.fire('Error', 'Category name is required', 'error');
    }

    // Collect attributes
    const attributes = [];
    document.querySelectorAll('.attribute-row').forEach(row => {
        const type = row.querySelector('.attr-type').value;
        const value = row.querySelector('.attr-value').value;
        if (value.trim()) {
            attributes.push({ type: type, value: value.trim() });
        }
    });

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                name: categoryName,
                attributes: attributes
            })
        });

        const result = await response.json();
        if (result.status === 'success') {
            Swal.fire('Saved!', 'Category and attributes added.', 'success')
                .then(() => location.reload());
        } else {
            Swal.fire('Error', result.message, 'error');
        }
    } catch (err) {
        Swal.fire('Error', 'Server connection failed', 'error');
    }
}