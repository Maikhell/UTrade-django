document.addEventListener('DOMContentLoaded', function () {
  const checkbox = document.getElementById('termsCheckbox');
  const signUpBtn = document.getElementById('signUpBtn');
  const form = document.getElementById('registerForm');
  const agreeBtn = document.getElementById('agreeTermsBtn');
  const termsModalEl = document.getElementById('termsModal');
  const termsBody = document.getElementById('termsBody');
  const scrollNotice = document.getElementById('scrollNotice');
  const termsHint = document.getElementById('termsHint');
  const studentInput = document.getElementById('id_student_no');

  const STUDENT_NO_LENGTH = 9;
  let termsRead = false; // becomes true once the user scrolls to the bottom

  // ----- Student number: digits only, max 9 -----
  if (studentInput) {
    const sanitize = function () {
      const cleaned = studentInput.value
        .replace(/\D/g, '')
        .slice(0, STUDENT_NO_LENGTH);
      if (studentInput.value !== cleaned) {
        studentInput.value = cleaned;
      }
    };

    sanitize(); // clean any prefilled value (e.g. after a failed submit)
    studentInput.addEventListener('input', sanitize); // typing, paste, drag-drop, mobile keyboards

    // Block non-digit keystrokes (letters, symbols, spaces)
    studentInput.addEventListener('keydown', function (e) {
      const allowedKeys = [
        'Backspace', 'Delete', 'Tab', 'Enter', 'Escape',
        'ArrowLeft', 'ArrowRight', 'Home', 'End'
      ];
      if (allowedKeys.includes(e.key) || e.ctrlKey || e.metaKey) return;
      if (!/^\d$/.test(e.key)) e.preventDefault();
    });
  }

  // ----- Terms: sign up only enabled when box is checked -----
  function updateSignUpState() {
    if (signUpBtn && checkbox) {
      signUpBtn.disabled = !checkbox.checked;
    }
  }
  updateSignUpState();

  function openTermsModal() {
    if (!termsModalEl || typeof bootstrap === 'undefined') return;
    bootstrap.Modal.getOrCreateInstance(termsModalEl).show();
  }

  // First time: clicking the checkbox opens the modal instead of checking it
  if (checkbox) {
    checkbox.addEventListener('click', function (e) {
      if (!termsRead && !checkbox.checked) {
        // (checked is already true here because the click toggled it)
      }
      if (!termsRead) {
        e.preventDefault();
        checkbox.checked = false;
        openTermsModal();
        return;
      }
      updateSignUpState();
    });

    checkbox.addEventListener('change', updateSignUpState);
  }

  // ----- Scroll-to-bottom detection inside the modal -----
  function isAtBottom(el) {
    return el.scrollTop + el.clientHeight >= el.scrollHeight - 5;
  }

  function checkScroll() {
    if (!termsBody || !agreeBtn) return;
    if (isAtBottom(termsBody)) {
      termsRead = true;
      agreeBtn.disabled = false;
      if (scrollNotice) scrollNotice.classList.add('d-none');
    }
  }

  if (termsBody) {
    termsBody.addEventListener('scroll', checkScroll);
  }

  if (termsModalEl) {
    termsModalEl.addEventListener('shown.bs.modal', function () {
      if (termsBody && !termsRead) termsBody.scrollTop = 0;
      checkScroll(); // in case the content already fits without scrolling
    });
  }

  // "I AGREE" checks the box and closes the modal
  if (agreeBtn) {
    agreeBtn.addEventListener('click', function () {
      if (!termsRead) return;
      if (checkbox) checkbox.checked = true;
      updateSignUpState();
      if (termsHint) termsHint.classList.add('d-none');
      if (termsModalEl && typeof bootstrap !== 'undefined') {
        bootstrap.Modal.getOrCreateInstance(termsModalEl).hide();
      }
    });
  }

  // ----- Confirm before submit -----
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();

      if (studentInput && studentInput.value.length !== STUDENT_NO_LENGTH) {
        if (typeof Swal !== 'undefined') {
          Swal.fire({
            title: 'Invalid Student Number',
            text: 'Student number must be exactly 9 digits.',
            icon: 'warning',
            confirmButtonColor: '#198754'
          });
        }
        studentInput.focus();
        return;
      }

      if (!checkbox || !checkbox.checked) {
        if (typeof Swal !== 'undefined') {
          Swal.fire({
            title: 'Terms Required',
            text: 'Please read and accept the Terms and Services before registering.',
            icon: 'warning',
            confirmButtonColor: '#198754'
          }).then(function () {
            openTermsModal();
          });
        } else {
          openTermsModal();
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

  // ----- Student number validation & alumni detection (on blur) -----
  if (studentInput) {
    studentInput.addEventListener('blur', function () {
      const studentNo = this.value.trim();
      if (!studentNo) return;

      if (studentNo.length < STUDENT_NO_LENGTH) {
        if (typeof Swal !== 'undefined') {
          Swal.fire({
            title: 'Incomplete Number',
            text: 'Student number must be exactly 9 digits.',
            icon: 'warning',
            confirmButtonColor: '#198754'
          });
        }
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