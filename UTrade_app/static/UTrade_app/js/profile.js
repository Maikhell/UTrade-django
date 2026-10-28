// --- 1. Handle Profile Update Submission ---
async function handleProfileSubmit(e) {
    // The re-verification dialog (inline script in profile.html) already
    // handled this submit, or the user just confirmed it. Don't ask twice.
    if (e.defaultPrevented) return;
    const flag = document.getElementById('confirm_reverify');
    if (flag && flag.value === '1') return;

    e.preventDefault(); // Stop the natural submit to show Swal
    const form = document.getElementById('profileForm');

    const result = await Swal.fire({
        title: 'Save changes?',
        text: "Your profile information will be updated.",
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#198754',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Yes, update it!',
    });

    if (result.isConfirmed) {
        Swal.fire({
            title: 'Updating...',
            allowOutsideClick: false,
            didOpen: () => { Swal.showLoading(); }
        });
        form.submit(); // Now the names and profile pic will actually save
    }
}

// --- 2. Handle Django Success/Error Messages ---
// The template renders one element per message, so show them one after another.
async function showDjangoMessages() {
    const containers = document.querySelectorAll('[id="django-messages"]');
    if (!containers.length) return;

    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
    });

    for (const el of containers) {
        const message = el.dataset.message;
        const tags = el.dataset.tags || '';

        await Toast.fire({
            icon: tags.includes('success') ? 'success'
                : (tags.includes('error') ? 'error'
                : (tags.includes('warning') ? 'warning' : 'info')),
            title: message
        });
    }
}

// --- 3. Initialize Listeners on Load ---
document.addEventListener('DOMContentLoaded', function () {
    showDjangoMessages();

    // Attach the submit handler to the profile form
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        profileForm.addEventListener('submit', handleProfileSubmit);
    }

    // Handle Verification Form Validation
    const verifForm = document.getElementById('verificationForm');
    if (verifForm) {
        verifForm.addEventListener('submit', function (e) {
            const errorDiv = document.getElementById('error-message');

            // Add data-role="{{ user.user_role }}" to the verification form in the
            // template. ({{ }} does not work inside a static .js file.)
            const role = verifForm.dataset.role || '';
            const firstName = document.getElementsByName('first_name')[0]?.value || "";
            const lastName = document.getElementsByName('last_name')[0]?.value || "";

            const missingFields = [];
            if (!firstName.trim()) missingFields.push("First Name");
            if (!lastName.trim()) missingFields.push("Last Name");

            // Only require academic info if they are NOT alumni
            if (role !== 'alumni') {
                const studentNo = document.getElementsByName('student_no')[0]?.value || "";
                const course = document.getElementsByName('course')[0]?.value || "";
                const section = document.getElementsByName('section')[0]?.value || "";

                if (!studentNo.trim()) missingFields.push("Student Number");
                if (!course.trim()) missingFields.push("Course");
                if (!section.trim()) missingFields.push("Section");
            }

            if (missingFields.length > 0) {
                e.preventDefault();
                errorDiv.innerHTML = `
                    <div class="alert alert-danger border-0 small">
                        <strong>Hold on!</strong> Save your profile details first. Missing: ${missingFields.join(', ')}.
                    </div>`;
                errorDiv.classList.remove('d-none');
            }
        });
    }
});

function previewAvatar(event) {
    const reader = new FileReader();
    reader.onload = function () {
        const output = document.getElementById('profile_preview');
        output.src = reader.result;
    };
    if (event.target.files[0]) {
        reader.readAsDataURL(event.target.files[0]);
    }
}