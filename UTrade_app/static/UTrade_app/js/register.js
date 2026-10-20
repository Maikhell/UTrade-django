document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('registerForm');
  const studentInput = document.getElementById('id_student_no');
  const termsAcceptedInput = document.getElementById('termsAccepted');

  const termsModalEl = document.getElementById('termsModal');
  const termsBody = document.getElementById('termsBody');
  const scrollNotice = document.getElementById('scrollNotice');
  const modalCheckbox = document.getElementById('modalTermsCheckbox');
  const agreeBtn = document.getElementById('agreeTermsBtn');

  const STUDENT_NO_LENGTH = 9;
  let termsAccepted = false;

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

    sanitize();
    studentInput.addEventListener('input', sanitize);

    studentInput.addEventListener('keydown', function (e) {
      const allowedKeys = [
        'Backspace', 'Delete', 'Tab', 'Enter', 'Escape',
        'ArrowLeft', 'ArrowRight', 'Home', 'End'
      ];
      if (allowedKeys.includes(e.key) || e.ctrlKey || e.metaKey) return;
      if (!/^\d$/.test(e.key)) e.preventDefault();
    });
  }

  // ----- Terms modal: scroll to bottom -> checkbox -> agree button -----
  function isAtBottom(el) {
    return el.scrollTop + el.clientHeight >= el.scrollHeight - 5;
  }

  function checkScroll() {
    if (!termsBody || !modalCheckbox) return;
    if (isAtBottom(termsBody)) {
      modalCheckbox.disabled = false;
      if (scrollNotice) scrollNotice.classList.add('d-none');
    }
  }

  function updateAgreeButton() {
    if (agreeBtn && modalCheckbox) {
      agreeBtn.disabled = !(modalCheckbox.checked && !modalCheckbox.disabled);
    }
  }

  if (termsBody) {
    termsBody.addEventListener('scroll', checkScroll);
  }

  if (modalCheckbox) {
    modalCheckbox.addEventListener('change', updateAgreeButton);
  }

  if (termsModalEl) {
    termsModalEl.addEventListener('shown.bs.modal', function () {
      checkScroll(); // in case the content already fits without scrolling
    });
  }

  function openTermsModal() {
    if (!termsModalEl || typeof bootstrap === 'undefined') return;
    bootstrap.Modal.getOrCreateInstance(termsModalEl).show();
  }

  function closeTermsModal() {
    if (!termsModalEl || typeof bootstrap === 'undefined') return;
    bootstrap.Modal.getOrCreateInstance(termsModalEl).hide();
  }

  // ----- Confirm and submit -----
  function confirmAndSubmit() {
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
  }

  // "I AGREE & CONTINUE": only works if the modal checkbox is checked
  if (agreeBtn) {
    agreeBtn.addEventListener('click', function () {
      if (!modalCheckbox || !modalCheckbox.checked || modalCheckbox.disabled) return;

      termsAccepted = true;
      if (termsAcceptedInput) termsAcceptedInput.disabled = false; // now sent as terms=on

      // Wait for the modal to finish closing before showing the Swal popup
      termsModalEl.addEventListener(
        'hidden.bs.modal',
        function onHidden() {
          termsModalEl.removeEventListener('hidden.bs.modal', onHidden);
          confirmAndSubmit();
        }
      );
      closeTermsModal();
    });
  }

  // ----- Form submit: validate, then require terms in the modal -----
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

      if (!termsAccepted) {
        openTermsModal();
        return;
      }

      confirmAndSubmit();
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