function submitBadWord() {
    const input = document.getElementById('new_bad_word');
    const word = input.value.trim();
    if (!word) return;


    const url = document.getElementById('btn-add-word').getAttribute('data-url');

    const formData = new FormData();
    formData.append('word', word);
    formData.append('csrfmiddlewaretoken', document.getElementById('csrf_token').value);

    fetch(url, {
        method: 'POST',
        body: formData
    })
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

function deleteBadWord(wordId) {
    if (!confirm('Remove this word from the filter?')) return;

    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', '{{ csrf_token }}');

    fetch(`/security/delete-word/${wordId}/`, {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const el = document.getElementById(`word-${wordId}`);
                el.classList.replace('animate__zoomIn', 'animate__zoomOut');
                setTimeout(() => el.remove(), 500);
            }
        });
}
function submitMeetup() {
    const input = document.getElementById('new_meetup_input');
    const locationValue = input.value.trim();
    if (!locationValue) return;

    const url = document.getElementById('btn-add-meetup').getAttribute('data-url');
    const formData = new FormData();

    formData.append('location', locationValue);
    formData.append('csrfmiddlewaretoken', document.getElementById('csrf_token').value);

    fetch(url, {
        method: 'POST',
        body: formData
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                const container = document.getElementById('meetups_container'); // Add this ID to your HTML
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
                location.reload();
            } else {
                Swal.fire('Error', data.message, 'error');
            }
        });
}

function deleteMeetup(locId) {
    if (!confirm('Remove this meetup spot?')) return;

    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', '{{ csrf_token }}');

    fetch(`/security/meetups/delete/${locId}/`, {
        method: 'POST',
        body: formData
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                document.getElementById(`meetup-${locId}`).remove();
            }
        });
}
function submitCategory() {
    const input = document.getElementById('new_category_input');
    const name = input.value.trim();
    if (!name) return;

    const url = document.getElementById('btn-add-category').getAttribute('data-url');

    const formData = new FormData();
    formData.append('name', name);
    formData.append('csrfmiddlewaretoken', document.getElementById('csrf_token').value);

    fetch(url, {
        method: 'POST',
        body: formData
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                const container = document.getElementById('categories_table_body'); // Target the <tbody>
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

function deleteCategory(catId) {
    if (!confirm('Are you sure? Products in this category might be affected.')) return;

    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', '{{ csrf_token }}');

    fetch(`/security/categories/delete/${catId}/`, {
        method: 'POST',
        body: formData
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                const row = document.getElementById(`category-${catId}`);
                row.classList.add('animate__animated', 'animate__fadeOutRight');
                setTimeout(() => row.remove(), 500);
            } else {
                Swal.fire('Error', data.message, 'error');
            }
        });
}