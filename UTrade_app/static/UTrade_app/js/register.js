document.addEventListener('DOMContentLoaded', function () {
    const checkbox = document.getElementById('termsCheckbox');
    const btn = document.getElementById('signUpBtn');
    const form = document.getElementById('registerForm');
    
    if (checkbox && btn && form) {

        // Manages the submit button state based on whether the user has checked the terms and conditions
        checkbox.addEventListener('change', function () {
            btn.disabled = !this.checked;
        });

        // Intercepts the standard form submission to inject a confirmation dialog before sending data
        form.addEventListener('submit', function (e) {
            e.preventDefault();

            Swal.fire({
                title: 'Confirm Registration',
                text: 'Ready to join the UTrade community?',
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#198754',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Yes, Sign me up!'
            }).then((result) => {
                // Only proceeds with the native form submission if the user clicks the confirmation button
                if (result.isConfirmed) {
                    Swal.fire({
                        title: 'Creating Account...',
                        allowOutsideClick: false,
                        didOpen: () => {
                            Swal.showLoading();
                        }
                    });
            
                    form.submit();
                }
            });
        });
    }
});