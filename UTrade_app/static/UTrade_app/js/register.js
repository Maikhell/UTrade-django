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
document.addEventListener('DOMContentLoaded', function() {
    const studentInput = document.getElementById('id_student_no');
    
    if (studentInput) {
        studentInput.addEventListener('blur', function() {
            const studentNo = this.value;
            if (!studentNo || studentNo.length < 4) return; // Basic length check

            const currentYear = new Date().getFullYear(); 
            const entryYear = parseInt(studentNo.substring(0, 4));
            
            console.log("Entry Year Detected:", entryYear); 

            // 1. Check for Future Years
            if (entryYear > currentYear) {
                Swal.fire({
                    title: 'Invalid Number',
                    text: 'Entry year cannot be in the future.',
                    icon: 'error',
                    confirmButtonColor: '#d33'
                });
                this.value = ''; // Clear the input
                return;
            }

            // 2. Check for "Expired" Student Numbers (older than 6 years)
            if (currentYear - entryYear > 6) {
                Swal.fire({
                    title: 'Invalid Student Number',
                    text: 'This student number is too old for registration.',
                    icon: 'warning',
                    confirmButtonColor: '#3085d6'
                });
                this.value = ''; // Clear the input
                return;
            }

            // 3. Alumni Detection (For years within the valid 4-6 year gap)
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
                    if (roleInput) {
                        if (result.isConfirmed) {
                            roleInput.value = 'alumni';
                            console.log("Role changed to: alumni");
                        } else {
                            roleInput.value = 'student';
                            console.log("Role remains: student");
                        }
                    }
                });
            }
        });
    } else {
        console.error("Could not find input with ID 'id_student_no'");
    }
});