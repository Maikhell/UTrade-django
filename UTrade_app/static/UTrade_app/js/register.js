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
document.addEventListener('DOMContentLoaded', function() {
    const studentInput = document.getElementById('id_student_no');
    
    if (studentInput) {
        studentInput.addEventListener('blur', function() {
            const studentNo = this.value;
            const currentYear = new Date().getFullYear(); 
            const entryYear = parseInt(studentNo.substring(0, 4));
            
            console.log("Entry Year Detected:", entryYear); 

            if (entryYear && (currentYear - entryYear) >= 4) {
                Swal.fire({
                    title: 'Alumni Detection',
                    text: `Is ${entryYear} your starting year? Are you an Alumnus?`,
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonText: 'Yes, Alumni',
                    cancelButtonText: 'No, Student',
                    confirmButtonColor: '#198754'
                }).then((result) => {
                    const roleInput = document.getElementById('id_user_role');
                    if (result.isConfirmed) {
                        roleInput.value = 'alumni';
                        console.log("Role changed to: alumni");
                    } else {
                        roleInput.value = 'student';
                        console.log("Role remains: student");
                    }
                });
            }
        });
    } else {
        console.error("Could not find input with ID 'id_student_no'");
    }
});