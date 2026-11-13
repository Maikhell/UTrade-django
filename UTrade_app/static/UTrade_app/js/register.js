document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('registerForm');
  const studentInput = document.getElementById('id_student_no');
  const termsAcceptedInput = document.getElementById('termsAccepted');
  const roleInput = document.getElementById('id_user_role');
  const alumniInput = document.getElementById('id_is_alumni');

  const termsModalEl = document.getElementById('termsModal');
  const termsBody = document.getElementById('termsBody');
  const scrollNotice = document.getElementById('scrollNotice');
  const modalCheckbox = document.getElementById('modalTermsCheckbox');
  const agreeBtn = document.getElementById('agreeTermsBtn');

  const STUDENT_NO_LENGTH = 9;
  // Same numbers as the server (alumni_utils.py); register.html passes them in.
  const data = (form && form.dataset) || {};
  const PROGRAM_YEARS = parseInt(data.programYears, 10) || 4;
  const ALUMNI_VALID_YEARS = parseInt(data.alumniValidYears, 10) || 1;
  const MAX_ENTRY_AGE = parseInt(data.maxEntryYears, 10) || 6;
  const CURRENT_AY = parseInt(data.currentAy, 10) || new Date().getFullYear();  // start year of this academic year
  const AY_END_MONTH = parseInt(data.ayEndMonth, 10) || 7;                      // academic year ends in July

  let termsAccepted = false;
  let alumniAnsweredFor = null; // student number the alumni question was already answered for
  let busy = false;             // stops a double click from opening two dialogs

  // ----- helpers -----
  function entryInfo(studentNo) {
    const year = parseInt(studentNo.substring(0, 4), 10);
    return { year: year, age: new Date().getFullYear() - year };
  }

  // Year level and alumni window, by academic year (August to July).
  function academicInfo(studentNo) {
    const year = parseInt(studentNo.substring(0, 4), 10);
    const expiry = new Date(year + PROGRAM_YEARS + ALUMNI_VALID_YEARS, AY_END_MONTH, 0); // last day of that month
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return {
      year: year,
      level: CURRENT_AY - year + 1,
      expiry: expiry,
      windowOpen: expiry.getTime() >= today.getTime()
    };
  }

  function formatDate(d) {
    return d.toLocaleDateString('en-PH', { year: 'numeric', month: 'long', day: 'numeric' });
  }

  function warn(title, text, icon) {
    if (typeof Swal !== 'undefined') {
      Swal.fire({
        title: title,
        text: text,
        icon: icon || 'warning',
        confirmButtonColor: '#198754'
      });
    }
  }

  // Returns {title, text, icon} when the entry year is not acceptable, otherwise null.
  function yearProblem(studentNo) {
    const info = entryInfo(studentNo);
    if (info.age < 0) {
      return { title: 'Invalid Number', text: 'Entry year cannot be in the future.', icon: 'error' };
    }
    if (info.age > MAX_ENTRY_AGE) {
      return {
        title: 'Invalid Student Number',
        text: 'This student number is too old for registration.',
        icon: 'warning'
      };
    }
    return null;
  }

  function setAlumni(flag) {
    if (alumniInput) alumniInput.value = flag ? '1' : '0';
    if (roleInput) roleInput.value = flag ? 'alumni' : 'student';
  }

  // ----- Student number: digits only, max 9 -----
  if (studentInput) {
    const sanitize = function () {
      const cleaned = studentInput.value
        .replace(/\D/g, '')
        .slice(0, STUDENT_NO_LENGTH);
      if (studentInput.value !== cleaned) {
        studentInput.value = cleaned;
      }
      // A different number means the earlier alumni answer no longer applies.
      if (studentInput.value !== alumniAnsweredFor) {
        alumniAnsweredFor = null;
        setAlumni(false);
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

  // ----- Alumni question (asked on submit, before the Terms modal) -----
  // Returns 'ok' to carry on, or 'cancel' to stop the sign-up.
  async function resolveAlumniStatus() {
    const studentNo = studentInput.value.trim();
    const info = academicInfo(studentNo);

    if (info.level <= PROGRAM_YEARS) {          // still within the program: regular student
      setAlumni(false);
      alumniAnsweredFor = studentNo;
      return 'ok';
    }
    if (alumniAnsweredFor === studentNo) return 'ok'; // already answered for this number

    const hasSwal = typeof Swal !== 'undefined';
    const expiryText = formatDate(info.expiry);

    // Alumni access for this batch has already ended.
    if (!info.windowOpen) {
      let stillStudent;
      if (hasSwal) {
        const r = await Swal.fire({
          title: 'Alumni access has ended',
          html:
            'Your student number starts with <b>' + info.year + '</b>. Alumni accounts stay active for ' +
            ALUMNI_VALID_YEARS + ' year(s) after graduation, which ended on <b>' + expiryText +
            '</b> for your batch, so alumni sign-up is no longer available.<br><br>' +
            'Are you still enrolled as a student?',
          icon: 'info',
          showCancelButton: true,
          confirmButtonText: "Yes, I'm still a student",
          cancelButtonText: 'Cancel',
          confirmButtonColor: '#198754',
          cancelButtonColor: '#6c757d',
          allowOutsideClick: false,
          allowEscapeKey: false
        });
        stillStudent = r.isConfirmed;
      } else {
        stillStudent = window.confirm(
          'Alumni access for the ' + info.year + ' batch ended on ' + expiryText +
          '. Are you still enrolled as a student?'
        );
      }
      if (!stillStudent) return 'cancel';
      setAlumni(false);
      alumniAnsweredFor = studentNo;
      return 'ok';
    }

    // Finished the program and still inside the alumni window: ask.
    let isAlumni;
    if (hasSwal) {
      const result = await Swal.fire({
        title: 'Are you an alumnus?',
        html:
          'Your student number starts with <b>' + info.year + '</b>, so your batch has finished the ' +
          PROGRAM_YEARS + '-year program.<br>Alumni accounts stay active until <b>' + expiryText +
          '</b> (' + ALUMNI_VALID_YEARS + ' year after graduation, when the CvSU email expires).<br><br>' +
          'Have you graduated?',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: "Yes, I'm an alumnus",
        cancelButtonText: "No, I'm still a student",
        confirmButtonColor: '#198754',
        cancelButtonColor: '#6c757d',
        allowOutsideClick: false,
        allowEscapeKey: false
      });
      isAlumni = result.isConfirmed;
    } else {
      isAlumni = window.confirm(
        'Your student number starts with ' + info.year + '. Are you an alumnus (already graduated)? ' +
        'Alumni access lasts until ' + expiryText + '.'
      );
    }

    setAlumni(isAlumni);
    alumniAnsweredFor = studentNo;
    return 'ok';
  }

  // ----- Confirm and submit -----
  function confirmAndSubmit() {
    const asAlumnus = alumniInput && alumniInput.value === '1';
    if (typeof Swal !== 'undefined') {
      Swal.fire({
        title: 'Confirm Registration',
        text: asAlumnus
          ? 'Ready to join the UTrade community as an alumnus?'
          : 'Ready to join the UTrade community?',
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

  // ----- Form submit: validate -> alumni question -> terms -> confirm -----
  if (form) {
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      if (busy) return;
      busy = true;

      try {
        const studentNo = studentInput ? studentInput.value.trim() : '';

        if (studentInput && studentNo.length !== STUDENT_NO_LENGTH) {
          warn('Invalid Student Number', 'Student number must be exactly 9 digits.');
          studentInput.focus();
          return;
        }

        const problem = studentInput ? yearProblem(studentNo) : null;
        if (problem) {
          warn(problem.title, problem.text, problem.icon);
          studentInput.value = '';
          studentInput.focus();
          return;
        }

        if (studentInput && (await resolveAlumniStatus()) === 'cancel') return;

        if (!termsAccepted) {
          openTermsModal();
          return;
        }

        confirmAndSubmit();
      } finally {
        busy = false;
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

  // ----- Student number check when leaving the field (the alumni question waits for submit) -----
  if (studentInput) {
    studentInput.addEventListener('blur', function () {
      const studentNo = this.value.trim();
      if (!studentNo) return;

      if (studentNo.length < STUDENT_NO_LENGTH) {
        warn('Incomplete Number', 'Student number must be exactly 9 digits.');
        return;
      }

      const problem = yearProblem(studentNo);
      if (problem) {
        warn(problem.title, problem.text, problem.icon);
        this.value = '';
      }
    });
  }
});