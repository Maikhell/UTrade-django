function showLoginPrompt() {
    const registerUrl = document.getElementById('register-url').value;

    Swal.fire({
        title: 'Join the Community!',
        text: 'You need an account to view full product details.',
        icon: 'info',
        showCancelButton: true,
        confirmButtonText: 'Register Now',
        confirmButtonColor: '#198754',
    }).then((result) => {
        if (result.isConfirmed) {
            window.location.href = registerUrl;
        }
    });
}

function showVerificationModal() {
    const userStatus = document.getElementById('user-verification-status').value;

    if (userStatus === 'unverified' || userStatus === 'Pending') {
        const modalEl = document.getElementById('verificationModal');
        if (modalEl) {
            const vModal = new bootstrap.Modal(modalEl);
            vModal.show();
        }
    } else {
        console.log("User status is:", userStatus, "- skipping modal.");
    }
}

// ---------- Filters, sorting and filter chips ----------
document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('filterForm');
    if (!form) return;

    var desktop = window.matchMedia('(min-width: 992px)');

    // Don't send empty params, so URLs stay clean (?category=3 instead of ?category=3&type=&org=)
    function clean() {
        Array.prototype.forEach.call(form.elements, function (el) {
            if (!el.name) return;
            if (el.type === 'radio' && !el.checked) return;
            if (el.value === '') el.disabled = true;
        });
    }

    function go() {
        clean();
        form.submit();
    }

    // "Apply filters" button
    form.addEventListener('submit', clean);

    // Restore fields if the user returns via the back button
    window.addEventListener('pageshow', function () {
        Array.prototype.forEach.call(form.elements, function (el) {
            el.disabled = false;
        });
    });

    // Desktop: apply as soon as a filter changes. Mobile: wait for "Apply filters".
    form.addEventListener('change', function () {
        if (desktop.matches) go();
    });

    // Sort always applies immediately
    var sort = document.getElementById('sortSelect');
    if (sort) sort.addEventListener('change', go);

    // Filter chips: clear one filter and reload
    document.querySelectorAll('[data-clear]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var field = form.elements[btn.getAttribute('data-clear')];
            if (field) field.value = '';
            go();
        });
    });
});