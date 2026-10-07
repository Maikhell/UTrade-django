document.addEventListener('DOMContentLoaded', function () {
  // ----- Terms checkbox → enable / disable Sign Up button -----
  const checkbox = document.getElementById('termsCheckbox');
  const btn = document.getElementById('signUpBtn');
  const form = document.getElementById('registerForm');
  const agreeBtn = document.getElementById('agreeTermsBtn');

  if (checkbox && btn) {
    btn.disabled = !checkbox.checked;

    checkbox.addEventListener('change', function () {
      btn.disabled = !this.checked;
    });
  }

  // "I AGREE" button inside the modal also checks the box
  if (agreeBtn && checkbox && btn) {
    agreeBtn.addEventListener('click', function () {
      checkbox.checked = true;
      btn.disabled = false;
      checkbox.dispatchEvent(new Event('change'));
    });
  }

  // Confirm before submit
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();

      if (!checkbox || !checkbox.checked) {
        if (typeof Swal !== 'undefined') {
          Swal.fire({
            title: 'Terms Required',
            text: 'Please accept the Terms and Services before registering.',
            icon: 'warning',
            confirmButtonColor: '#198754'
          });
        }
        return;
      }

      if (typeof Swal !== 'undefined') {
        Swal.fire({
          title: 'Confirm Registration',
          text: 'Ready to join the UTrade community?',
          icon: 'question',
          showCancelButton: true,
          confirmButtonColor: '#198754',
          cancelButtonColor: '#6c757d',
          confirmButtonText: 'Yes, Sign me up!'
        }).then(function (result) {
          if (result.isConfirmed) {
            Swal.fire({
              title: 'Creating Account...',
              allowOutsideClick: false,
              didOpen: function () {
                Swal.showLoading();
              }
            });
            form.submit();
          }
        });
      } else {
        form.submit();
      }
    });
  }

  // ----- Password visibility toggles -----
  document.querySelectorAll('.toggle-password').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const targetId = this.getAttribute('data-target');
      const input = document.getElementById(targetId);
      if (!input) return;
      const icon = this.querySelector('i');
      if (input.type === 'password') {
        input.type = 'text';
        if (icon) {
          icon.classList.remove('bi-eye');
          icon.classList.add('bi-eye-slash');
        }
      } else {
        input.type = 'password';
        if (icon) {
          icon.classList.remove('bi-eye-slash');
          icon.classList.add('bi-eye');
        }
      }
    });
  });

  // ----- Student number validation & alumni detection -----
  const studentInput = document.getElementById('id_student_no');

  if (studentInput) {
    studentInput.addEventListener('blur', function () {
      const studentNo = this.value.trim();
      if (!studentNo || studentNo.length < 4) return;

      if (!/^\d+$/.test(studentNo)) {
        if (typeof Swal !== 'undefined') {
          Swal.fire({
            title: 'Invalid Number',
            text: 'Student number must contain only digits.',
            icon: 'error',
            confirmButtonColor: '#d33'
          });
        }
        this.value = '';
        return;
      }

      const currentYear = new Date().getFullYear();
      const entryYear = parseInt(studentNo.substring(0, 4), 10);

      if (entryYear > currentYear) {
        if (typeof Swal !== 'undefined') {
          Swal.fire({
            title: 'Invalid Number',
            text: 'Entry year cannot be in the future.',
            icon: 'error',
            confirmButtonColor: '#d33'
          });
        }
        this.value = '';
        return;
      }

      if (currentYear - entryYear > 6) {
        if (typeof Swal !== 'undefined') {
          Swal.fire({
            title: 'Invalid Student Number',
            text: 'This student number is too old for registration.',
            icon: 'warning',
            confirmButtonColor: '#3085d6'
          });
        }
        this.value = '';
        return;
      }

      if (entryYear && currentYear - entryYear >= 4) {
        if (typeof Swal !== 'undefined') {
          Swal.fire({
            title: 'Alumni Detection',
            text: 'Is ' + entryYear + ' your starting year? Are you an Alumnus?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Yes, Alumni',
            cancelButtonText: 'No, Student',
            confirmButtonColor: '#198754'
          }).then(function (result) {
            const roleInput = document.getElementById('id_user_role');
            if (roleInput) {
              roleInput.value = result.isConfirmed ? 'alumni' : 'student';
            }
          });
        }
      }
    });
  }
});