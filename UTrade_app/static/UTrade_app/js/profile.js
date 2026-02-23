async function handleProfileSubmit() {
    const form = document.getElementById('profileForm');
    
    if (!form) {
        console.error("Form with ID 'profileForm' not found!");
        return;
    }

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
            icon: tags === 'success' ? 'success' : 'info',
            title: message
        });
    }
}
document.addEventListener('DOMContentLoaded', showDjangoMessages);

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