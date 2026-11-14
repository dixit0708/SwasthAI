/**
 * SwasthAI — shared UI helpers for the signed-in app pages.
 * Rendering helpers for loading, empty and error states, plus toasts,
 * confirm dialogs and date formatting. Pairs with css/app-pages.css.
 *
 * Everything that reaches innerHTML goes through AppUI.esc() first, so
 * user-entered text (names, notes, file names) can never run as markup.
 */
const AppUI = (() => {
  const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

  function esc(value) {
    return String(value === null || value === undefined ? '' : value).replace(/[&<>"']/g, (c) => ESCAPES[c]);
  }

  // "2026-03-15" or an ISO timestamp -> "15 Mar 2026". Date-only strings are
  // read as local dates so they never shift by a day across time zones.
  function parseDate(value) {
    if (!value) return null;
    if (value instanceof Date) return value;
    const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (dateOnly) return new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]));
    // The API sends UTC timestamps without a zone suffix.
    const iso = /[zZ]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`;
    const parsed = new Date(iso);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function fmtDate(value, options) {
    const date = parseDate(value);
    if (!date) return '';
    return date.toLocaleDateString('en-IN', options || { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function fmtDateLong(value) {
    return fmtDate(value, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  }

  // "14:30" -> "2:30 pm"
  function fmtTime(hhmm) {
    const match = /^(\d{2}):(\d{2})$/.exec(hhmm || '');
    if (!match) return hhmm || '';
    const hours = Number(match[1]);
    const suffix = hours >= 12 ? 'pm' : 'am';
    return `${hours % 12 || 12}:${match[2]} ${suffix}`;
  }

  function todayIso() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  }

  // "Today", "Tomorrow", "In 5 days", "3 days ago" for a date-only value.
  function relativeDay(value) {
    const date = parseDate(value);
    if (!date) return '';
    const start = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const days = Math.round((start(date) - start(new Date())) / 86400000);
    if (days === 0) return 'Today';
    if (days === 1) return 'Tomorrow';
    if (days === -1) return 'Yesterday';
    return days > 0 ? `In ${days} days` : `${Math.abs(days)} days ago`;
  }

  function skeletonRows(count = 3) {
    return Array.from({ length: count }, () => `
      <div class="row-item" aria-hidden="true">
        <span class="skeleton skeleton--avatar"></span>
        <div class="row-item__main" style="display:grid; gap:8px;">
          <span class="skeleton skeleton--title"></span>
          <span class="skeleton skeleton--line" style="width:70%;"></span>
        </div>
      </div>`).join('');
  }

  function state({ icon = 'fa-inbox', title, text = '', actionHtml = '', error = false }) {
    return `
      <div class="state${error ? ' state--error' : ''}" ${error ? 'role="alert"' : ''}>
        <span class="state__icon"><i class="fas ${esc(icon)}" aria-hidden="true"></i></span>
        <h3 class="state__title">${esc(title)}</h3>
        ${text ? `<p class="state__text">${esc(text)}</p>` : ''}
        ${actionHtml}
      </div>`;
  }

  function errorState(message, retryId) {
    return state({
      icon: 'fa-triangle-exclamation',
      title: "We couldn't load this",
      text: message || 'Please check your connection and try again.',
      actionHtml: retryId ? `<button type="button" class="btn btn-outline btn-compact" id="${esc(retryId)}"><i class="fas fa-rotate-right" aria-hidden="true"></i>&nbsp; Try again</button>` : '',
      error: true
    });
  }

  function toastRegion() {
    let region = document.getElementById('toastRegion');
    if (!region) {
      region = document.createElement('div');
      region.id = 'toastRegion';
      region.className = 'toast-region';
      region.setAttribute('role', 'status');
      region.setAttribute('aria-live', 'polite');
      document.body.appendChild(region);
    }
    return region;
  }

  function toast(message, type = 'ok') {
    const el = document.createElement('div');
    el.className = `toast${type === 'error' ? ' toast--error' : ''}`;
    el.innerHTML = `<i class="fas ${type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-check'}" aria-hidden="true"></i><span>${esc(message)}</span>`;
    toastRegion().appendChild(el);
    setTimeout(() => el.remove(), type === 'error' ? 6000 : 3500);
  }

  // Promise-based confirm built on <dialog>, which gives focus trapping and
  // Escape-to-close for free.
  function confirm({ title, text, confirmLabel = 'Confirm', danger = false }) {
    return new Promise((resolve) => {
      const dialog = document.createElement('dialog');
      dialog.className = 'sheet';
      dialog.innerHTML = `
        <div class="sheet__head"><h2>${esc(title)}</h2></div>
        <div class="sheet__body"><p style="margin:0; color:var(--text-secondary); line-height:1.6;">${esc(text)}</p></div>
        <div class="sheet__foot">
          <button type="button" class="btn btn-outline btn-compact" data-answer="no">Keep it</button>
          <button type="button" class="btn ${danger ? 'btn-danger-outline' : 'btn-primary'} btn-compact" data-answer="yes">${esc(confirmLabel)}</button>
        </div>`;
      document.body.appendChild(dialog);
      let answer = false;
      dialog.addEventListener('click', (e) => {
        const button = e.target.closest('[data-answer]');
        if (!button) return;
        answer = button.dataset.answer === 'yes';
        dialog.close();
      });
      dialog.addEventListener('close', () => {
        dialog.remove();
        resolve(answer);
      });
      dialog.showModal();
    });
  }

  function setBusy(button, busy, busyLabel) {
    if (!button) return;
    if (busy) {
      button.dataset.label = button.innerHTML;
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
      if (busyLabel) button.textContent = busyLabel;
    } else {
      button.disabled = false;
      button.removeAttribute('aria-busy');
      if (button.dataset.label) button.innerHTML = button.dataset.label;
    }
  }

  // Friendly text for a failed request, never a raw technical error.
  function errorText(err) {
    return (err && err.message) || 'Something went wrong. Please try again.';
  }

  // ── Saved risk-assessment rows (dashboard + AI Insights history) ────────
  const ASSESSMENTS = {
    diabetes: { icon: 'fa-droplet', tone: 'blue', page: 'prediction-diabetes-choose.html', specialty: 'endocrinology' },
    heart: { icon: 'fa-heart-pulse', tone: 'red', page: 'prediction-heart.html', specialty: 'cardiology' },
    liver: { icon: 'fa-flask', tone: 'violet', page: 'prediction-liver-choose.html', specialty: 'gastroenterology' },
    skin: { icon: 'fa-hand-dots', tone: 'amber', page: 'prediction-skin.html', specialty: 'dermatology' }
  };

  function assessmentInfo(key) {
    return ASSESSMENTS[key] || { icon: 'fa-notes-medical', tone: 'teal', page: 'predictions.html', specialty: '' };
  }

  // Wording stays non-diagnostic: a "risk indicator", never a finding.
  function riskPill(item) {
    if (item.assessment === 'skin') return '<span class="pill pill--info">Image assessment</span>';
    if (item.is_elevated === true) return '<span class="pill pill--warn">Higher risk indicator</span>';
    if (item.is_elevated === false) return '<span class="pill pill--ok">Lower risk indicator</span>';
    return '';
  }

  function predictionRow(item, { withDelete = false } = {}) {
    const info = assessmentInfo(item.assessment);
    const forWhom = item.family_member_name ? ` &middot; for ${esc(item.family_member_name)}` : '';
    let detail = '';
    if (item.assessment === 'skin' && item.label) {
      detail = `Closest visual match: ${esc(item.label)}. Only a dermatologist can confirm.`;
    } else if (typeof item.risk_probability === 'number') {
      detail = `Estimated risk score ${Math.round(item.risk_probability * 100)}%`;
    }
    const meter = typeof item.risk_probability === 'number' && item.assessment !== 'skin'
      ? `<span class="meter" aria-hidden="true"><span class="meter__fill${item.is_elevated ? ' meter__fill--elevated' : ''}" style="width:${Math.max(4, Math.min(100, Math.round(item.risk_probability * 100)))}%"></span></span>`
      : '';
    return `
      <li class="row-item" data-id="${esc(item.id)}">
        <span class="row-item__icon row-item__icon--${info.tone}"><i class="fas ${info.icon}" aria-hidden="true"></i></span>
        <div class="row-item__main">
          <div class="row-item__title">${esc(item.condition_label)}${forWhom}</div>
          <div class="row-item__meta">${esc(fmtDate(item.created_at))}${detail ? ` &middot; ${detail}` : ''}</div>
        </div>
        <div class="row-item__aside">
          ${meter}
          ${riskPill(item)}
          ${withDelete ? `<button type="button" class="icon-btn icon-btn--danger" data-action="delete-result" aria-label="Delete this saved result"><i class="fas fa-trash-can" aria-hidden="true"></i></button>` : ''}
        </div>
      </li>`;
  }

  return {
    esc, parseDate, fmtDate, fmtDateLong, fmtTime, todayIso, relativeDay,
    skeletonRows, state, errorState, toast, confirm, setBusy, errorText,
    assessmentInfo, riskPill, predictionRow
  };
})();
