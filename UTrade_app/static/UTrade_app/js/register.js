document.addEventListener('DOMContentLoaded', function () {
    const checkbox = document.getElementById('termsCheckbox');
    const btn = document.getElementById('signUpBtn');
    const form = document.getElementById('registerForm');
    
    if (checkbox && btn && form) {

        checkbox.addEventListener('change', function () {
            btn.disabled = !this.checked;
        });

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