function showLoginPrompt() {
    const loginUrl = document.getElementById('login-url').value;

    Swal.fire({
        title: 'Join the Community!',
        text: 'You need to be logged in to view full product details.',
        icon: 'info',
        showCancelButton: true,
        confirmButtonText: 'Login Now',
        confirmButtonColor: '#198754',
    }).then((result) => {
        if (result.isConfirmed) {
            window.location.href = loginUrl;
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