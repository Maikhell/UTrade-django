function confirmLogout() {
    Swal.fire({
        title: 'Logging out?',
        text: "Are you sure you want to end your session?",
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#dc3545', 
        cancelButtonColor: '#6c757d',  
        confirmButtonText: 'Yes, logout',
        cancelButtonText: 'Stay logged in',
        reverseButtons: true 
    }).then((result) => {
        if (result.isConfirmed) {
            document.getElementById('logout-form').submit();
        }
    });
}