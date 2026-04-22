// --- 1. Handle Profile Update Submission ---
async function handleProfileSubmit(e) {
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
function showDjangoMessages() {
    const messageContainer = document.getElementById('django-messages');
    if (messageContainer) {
        const message = messageContainer.dataset.message;
        const tags = messageContainer.dataset.tags;

        const Toast = Swal.mixin({
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 3000,
            timerProgressBar: true,
        });

        Toast.fire({
            icon: tags === 'success' ? 'success' : (tags === 'error' ? 'error' : 'info'),
            title: message
        });
    }
}

// --- 3. Initialize Listeners on Load ---
document.addEventListener('DOMContentLoaded', function() {
    showDjangoMessages();

    // Attach the submit handler to the profile form
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        profileForm.addEventListener('submit', handleProfileSubmit);
    }

    // Handle Verification Form Validation
    const verifForm = document.getElementById('verificationForm');
    if (verifForm) {
        verifForm.addEventListener('submit', function(e) {
            const errorDiv = document.getElementById('error-message');
            
            // Get user data and role from hidden inputs or data-attributes
            // It is better to use the values currently in the inputs
            const role = "{{ user.user_role }}"; // Passed from Django context
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
    reader.onload = function() {
        const output = document.getElementById('profile_preview');
        output.src = reader.result;
    };
    if (event.target.files[0]) {
        reader.readAsDataURL(event.target.files[0]);
    }
}