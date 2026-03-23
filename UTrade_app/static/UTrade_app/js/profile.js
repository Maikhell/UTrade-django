async function handleProfileSubmit() {
    const form = document.getElementById('profileForm');
    
    if (!form) {
        console.error("Form with ID 'profileForm' not found!");
        return;
    }

    // Intercepts the submit action to present a visual confirmation dialog before the page reloads
    const result = await Swal.fire({
        title: 'Save changes?',
        text: "Your profile information will be updated.",
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#198754', 
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Yes, update it!',
        cancelButtonText: 'No, cancel'
    });

    if (result.isConfirmed) {
        // Displays a non-closable loading state to prevent multiple submissions while the server processes
        Swal.fire({
            title: 'Updating...',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });
        form.submit();
    }
}

function showDjangoMessages() {
    const messageContainer = document.getElementById('django-messages');
    if (messageContainer) {
        // Extracts data attributes from the HTML container to bridge Django backend alerts to the JavaScript UI
        const message = messageContainer.dataset.message;
        const tags = messageContainer.dataset.tags;

        // Configures a non-intrusive notification (Toast) that appears briefly at the corner of the screen
        const Toast = Swal.mixin({
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 3000,
            timerProgressBar: true,
        });

        Toast.fire({
            icon: tags === 'success' ? 'success' : 'info',
            title: message
        });
    }
}

// Ensures backend alerts are checked and displayed immediately after the DOM is fully constructed
document.addEventListener('DOMContentLoaded', showDjangoMessages);

function previewAvatar(event) {
    const reader = new FileReader();
    
    // Updates the image source in real-time by reading the file content into a base64 string
    reader.onload = function() {
        const output = document.getElementById('profile_preview');
        output.src = reader.result;
    };
    
    if (event.target.files[0]) {
        reader.readAsDataURL(event.target.files[0]);
    }
}