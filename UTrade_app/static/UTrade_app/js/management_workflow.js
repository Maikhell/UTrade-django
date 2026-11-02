(function () {
  'use strict';

  var cfg = window.WF_CONFIG || {};
  var NOUN = cfg.noun || 'order';
  var MAX_BATCH = 20;
  var csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
  var CSRF = csrfInput ? csrfInput.value : '';

  var ESTIMATE_OPTIONS = {
    '1 day': '1 day',
    '1-2 days': '1–2 days',
    '1-3 days': '1–3 days',
    '3-4 days': '3–4 days',
    'datetime': 'Specific date & time…',
    'Custom': 'Custom text…'
  };

  var REJECT_REASONS = {
    'Out of stock': 'Item(s) out of stock',
    'Pricing/Listing error': 'Pricing or product listing error',
    'Buyer request': 'Buyer requested cancellation',
    'Unable to fulfill': 'Unable to fulfill order',
    'Other': 'Other'
  };

  var ACTION_TEXT = {
    accept: { title: 'Accept {who}?', confirm: 'Accept' },
    processing: { title: 'Move {who} to Processing?', confirm: 'Confirm' },
    awaiting_payment: { title: 'Mark {who} as Awaiting Payment?', confirm: 'Confirm' },
    waiting_stocks: { title: 'Mark {who} as Waiting for Stocks?', confirm: 'Confirm' },
    ready: { title: 'Mark {who} Ready for Pickup?', confirm: 'Confirm' },
    complete: { title: 'Mark {who} as Completed?', confirm: 'Confirm' }
  };

  function getChecked(group) {
    return Array.prototype.map.call(
      document.querySelectorAll('.' + group + '-check:checked'),
      function (el) { return el.value; }
    );
  }

  function whoText(n) {
    return n > 1 ? n + ' ' + NOUN + 's' : 'this ' + NOUN;
  }

  // ---------- selection counters / enabled buttons ----------
  function refreshCounts() {
    document.querySelectorAll('[data-wf-count]').forEach(function (el) {
      var group = el.getAttribute('data-wf-count');
      var n = getChecked(group).length;
      el.textContent = n ? n + ' selected' : 'Select up to ' + MAX_BATCH;
      var bar = el.closest('.wf-batch');
      if (bar) {
        bar.querySelectorAll('[data-wf-needs]').forEach(function (b) { b.disabled = n === 0; });
      }
    });
  }

  document.addEventListener('change', function (e) {
    if (e.target.classList && (e.target.classList.contains('wf-check') || e.target.hasAttribute('data-wf-all'))) {
      refreshCounts();
    }
  });
  document.addEventListener('DOMContentLoaded', refreshCounts);

  window.toggleAll = function (group, checked) {
    document.querySelectorAll('.' + group + '-check').forEach(function (el) { el.checked = checked; });
    refreshCounts();
  };

  // ---------- server call ----------
  async function postBatch(action, ids, extra) {
    if (!ids.length) {
      Swal.fire('No selection', 'Select at least one ' + NOUN + '.', 'info');
      return;
    }
    if (ids.length > MAX_BATCH) {
      Swal.fire('Limit exceeded', 'You can process at most ' + MAX_BATCH + ' ' + NOUN + 's at a time.', 'warning');
      return;
    }
    var body = Object.assign({ action: action, order_ids: ids }, extra || {});
    try {
      var res = await fetch(cfg.batchUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': CSRF,
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(body)
      });
      var data = await res.json();
      if (data.success) {
        await Swal.fire({ title: 'Done', text: data.message || 'Updated.', icon: 'success', confirmButtonColor: '#198754' });
        location.reload();
      } else {
        Swal.fire({ title: 'Error', text: data.message || 'Failed.', icon: 'error', confirmButtonColor: '#198754' });
      }
    } catch (err) {
      Swal.fire({ title: 'Error', text: 'Could not reach the server.', icon: 'error', confirmButtonColor: '#198754' });
    }
  }

  // ---------- estimated pickup prompt ----------
  function nowLocalInput() {
    var d = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
    return d.toISOString().slice(0, 16);
  }

  function formatDateTime(value) {
    return new Date(value).toLocaleString('en-PH', {
      month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit'
    });
  }

  async function promptEstimate() {
    var first = await Swal.fire({
      title: 'Estimated pickup',
      input: 'select',
      inputOptions: ESTIMATE_OPTIONS,
      inputPlaceholder: 'Select an estimate',
      showCancelButton: true,
      confirmButtonColor: '#198754',
      confirmButtonText: 'Set',
      inputValidator: function (v) { return !v && 'Please select an option'; }
    });
    var choice = first.value;
    if (!choice) return null;

    if (choice === 'datetime') {
      var dt = await Swal.fire({
        title: 'Pickup date & time',
        input: 'datetime-local',
        inputAttributes: { min: nowLocalInput() },
        showCancelButton: true,
        confirmButtonColor: '#198754',
        inputValidator: function (v) { return !v && 'Pick a date and time'; }
      });
      return dt.value ? formatDateTime(dt.value) : null;
    }
    if (choice === 'Custom') {
      var custom = await Swal.fire({
        title: 'Custom estimate',
        input: 'text',
        inputPlaceholder: 'e.g. 5 days, by Friday…',
        inputAttributes: { maxlength: 50 },
        showCancelButton: true,
        confirmButtonColor: '#198754',
        inputValidator: function (v) { return !v && 'Required'; }
      });
      return custom.value || null;
    }
    return choice;
  }

  async function setEstimateFor(ids) {
    if (!ids.length) {
      Swal.fire('No selection', 'Select at least one ' + NOUN + '.', 'info');
      return;
    }
    var est = await promptEstimate();
    if (!est) return;
    return postBatch('set_estimate', ids, { estimated_pickup: est });
  }

  // ---------- one entry point for single + batch actions ----------
  async function runAction(ids, action) {
    if (!ids.length) {
      Swal.fire('No selection', 'Select at least one ' + NOUN + '.', 'info');
      return;
    }
    if (ids.length > MAX_BATCH) {
      Swal.fire('Limit exceeded', 'Max ' + MAX_BATCH + ' ' + NOUN + 's per batch.', 'warning');
      return;
    }

    if (action === 'set_estimate') return setEstimateFor(ids);

    var who = whoText(ids.length);

    if (action === 'reject') {
      var picked = await Swal.fire({
        title: 'Reject ' + who + '?',
        input: 'select',
        inputOptions: REJECT_REASONS,
        inputPlaceholder: 'Select a reason',
        showCancelButton: true,
        confirmButtonColor: '#dc3545',
        confirmButtonText: 'Reject',
        inputValidator: function (v) { return !v && 'Please select a reason'; }
      });
      if (!picked.value) return;
      var note = '';
      if (picked.value === 'Other') {
        var other = await Swal.fire({
          title: 'Please specify the reason',
          input: 'text',
          inputPlaceholder: 'Rejection details…',
          showCancelButton: true,
          confirmButtonColor: '#dc3545',
          inputValidator: function (v) { return !v && 'Required'; }
        });
        if (!other.value) return;
        note = other.value;
      }
      return postBatch('reject', ids, { reason: picked.value, note: note });
    }

    var extra = {};
    if (action === 'accept') {
      var est = await promptEstimate();          // optional: cancelling skips the estimate
      if (est) extra.estimated_pickup = est;
    }

    var text = ACTION_TEXT[action] || { title: 'Confirm?', confirm: 'OK' };
    var ok = await Swal.fire({
      title: text.title.replace('{who}', who),
      icon: 'question',
      showCancelButton: true,
      confirmButtonColor: '#198754',
      confirmButtonText: text.confirm
    });
    if (!ok.isConfirmed) return;
    return postBatch(action, ids, extra);
  }

  window.singleAction = function (id, action) { return runAction([String(id)], action); };
  window.batchAction = function (group, action) { return runAction(getChecked(group), action); };
  window.setEstimate = function (id) { return setEstimateFor([String(id)]); };
  window.batchSetEstimate = function (group) { return setEstimateFor(getChecked(group)); };

  // Close the details dialog first, then run the action (prompts can't take focus inside a modal)
  window.modalAction = function (modalId, id, action) {
    var el = document.getElementById(modalId);
    var instance = el && window.bootstrap ? bootstrap.Modal.getInstance(el) : null;
    if (!instance) return window.singleAction(id, action);
    el.addEventListener('hidden.bs.modal', function handler() {
      el.removeEventListener('hidden.bs.modal', handler);
      window.singleAction(id, action);
    });
    instance.hide();
  };
})();