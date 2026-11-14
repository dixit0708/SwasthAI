/**
 * SwasthAI — Medical records.
 * Two views:
 *   1. Stored records and documents (the /family/records API), with search,
 *      filters, add, open, download and delete.
 *   2. Lab reports the user has analysed (/report-analysis/history), each
 *      of which can be reopened in full.
 */
(() => {
  const recList = document.getElementById('recList');
  const reportList = document.getElementById('reportList');
  if (!recList || !reportList) return;

  const field = (id) => document.getElementById(id);
  const recDialog = field('recDialog');
  const reportDialog = field('reportDialog');
  const MAX_FILE_BYTES = 15 * 1024 * 1024;
  const REPORT_PAGE_SIZE = 8;

  const state = { members: [], records: [], reportPage: 1, reportsLoaded: false };

  const CATEGORY_ICONS = {
    'Lab Report': ['fa-vial', 'teal'],
    'Imaging Report': ['fa-x-ray', 'blue'],
    Prescription: ['fa-prescription', 'violet'],
    'Discharge Summary': ['fa-hospital', 'amber'],
    'Doctor Consultation': ['fa-user-doctor', 'blue'],
    Vaccination: ['fa-syringe', 'teal']
  };

  // ── Tabs ────────────────────────────────────────────────────────────────
  function showTab(name) {
    const reports = name === 'reports';
    field('tabDocuments').setAttribute('aria-selected', String(!reports));
    field('tabReports').setAttribute('aria-selected', String(reports));
    field('panelDocuments').hidden = reports;
    field('panelReports').hidden = !reports;
    field('recAddBtn').hidden = reports;
    if (reports && !state.reportsLoaded) loadReports();
  }
  field('tabDocuments').addEventListener('click', () => { history.replaceState(null, '', '#documents'); showTab('documents'); });
  field('tabReports').addEventListener('click', () => { history.replaceState(null, '', '#reports'); showTab('reports'); });

  // ── Stored records ──────────────────────────────────────────────────────
  function fileSize(bytes) {
    if (!bytes) return '';
    return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  function recordRow(rec) {
    const [icon, tone] = CATEGORY_ICONS[rec.category] || ['fa-file-medical', 'teal'];
    return `
      <li class="row-item" data-id="${AppUI.esc(rec.id)}" style="align-items:flex-start;">
        <span class="row-item__icon row-item__icon--${tone}"><i class="fas ${icon}" aria-hidden="true"></i></span>
        <div class="row-item__main">
          <div class="row-item__title">${AppUI.esc(rec.title)}</div>
          <div class="row-item__meta">${AppUI.esc(rec.category)} &middot; ${AppUI.esc(AppUI.fmtDate(rec.record_date))} &middot; ${AppUI.esc(rec.member_name || 'Profile')}</div>
          ${rec.provider ? `<div class="row-item__meta"><i class="fas fa-hospital" aria-hidden="true"></i> ${AppUI.esc(rec.provider)}</div>` : ''}
          ${rec.notes ? `<div class="row-item__meta">${AppUI.esc(rec.notes)}</div>` : ''}
          ${rec.has_document ? `<div class="row-item__meta"><i class="fas fa-paperclip" aria-hidden="true"></i> ${AppUI.esc(rec.file_name || 'Attached document')}${rec.file_size ? ` (${fileSize(rec.file_size)})` : ''}</div>` : ''}
        </div>
        <div class="row-item__aside">
          ${rec.has_document ? `
            <button type="button" class="btn btn-outline btn-compact" data-action="open"><i class="fas fa-eye" aria-hidden="true"></i>&nbsp; Open</button>
            <button type="button" class="icon-btn" data-action="download" aria-label="Download ${AppUI.esc(rec.file_name || 'document')}"><i class="fas fa-download" aria-hidden="true"></i></button>` : ''}
          <button type="button" class="icon-btn icon-btn--danger" data-action="delete" aria-label="Delete ${AppUI.esc(rec.title)}"><i class="fas fa-trash-can" aria-hidden="true"></i></button>
        </div>
      </li>`;
  }

  async function loadRecords() {
    recList.innerHTML = AppUI.skeletonRows(3);
    try {
      if (!state.members.length) {
        state.members = await CareProfiles.list();
        field('recMemberFilter').innerHTML = `<option value="">Everyone</option>${CareProfiles.optionsHtml(state.members, '')}`;
        field('recMemberFilter').hidden = state.members.length < 2;
      }
      if (!state.members.length) {
        recList.innerHTML = CareProfiles.emptyStateHtml('Records');
        return;
      }
      const filters = {
        memberId: field('recMemberFilter').value,
        category: field('recCategoryFilter').value,
        search: field('recSearch').value.trim()
      };
      state.records = await SwasthAPI.family.listRecords(filters);
      if (!state.records.length) {
        const filtered = filters.memberId || filters.category || filters.search;
        recList.innerHTML = AppUI.state(filtered
          ? { icon: 'fa-magnifying-glass', title: 'No records match', text: 'Try a different search or clear the filters.' }
          : {
              icon: 'fa-folder-open',
              title: 'No records stored yet',
              text: 'Add prescriptions, lab reports and discharge summaries so they are always at hand.',
              actionHtml: '<button type="button" class="btn btn-primary btn-compact" data-action="add">Add your first record</button>'
            });
        return;
      }
      recList.innerHTML = `<ul class="rows">${state.records.map(recordRow).join('')}</ul>`;
    } catch (err) {
      recList.innerHTML = AppUI.errorState(AppUI.errorText(err), 'recRetry');
      field('recRetry')?.addEventListener('click', loadRecords);
    }
  }

  function openRecordForm() {
    if (!state.members.length) {
      AppUI.toast('Add a profile first, then you can add records.', 'error');
      return;
    }
    field('recForm').reset();
    field('recMember').innerHTML = CareProfiles.optionsHtml(state.members, field('recMemberFilter').value || state.members[0].id);
    field('recDate').value = AppUI.todayIso();
    field('recDate').max = AppUI.todayIso();
    field('recFormError').hidden = true;
    recDialog.showModal();
    field('recTitle').focus();
  }

  field('recForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const error = field('recFormError');
    error.hidden = true;
    const title = field('recTitle').value.trim();
    const date = field('recDate').value;
    const file = field('recFile').files[0];

    let problem = '';
    if (!title) problem = 'Please give the record a title.';
    else if (!date) problem = 'Please enter the date on the record.';
    else if (date > AppUI.todayIso()) problem = 'The record date cannot be in the future.';
    else if (file && file.size > MAX_FILE_BYTES) problem = 'This file is larger than 15 MB. Please choose a smaller one.';
    else if (file && !/\.(pdf|jpe?g|png)$/i.test(file.name)) problem = 'Please attach a PDF, JPG or PNG file.';
    if (problem) {
      error.textContent = problem;
      error.hidden = false;
      return;
    }

    const formData = new FormData();
    formData.append('member_id', field('recMember').value);
    formData.append('title', title);
    formData.append('category', field('recCategory').value);
    formData.append('record_date', date);
    if (field('recProvider').value.trim()) formData.append('provider', field('recProvider').value.trim());
    if (field('recNotes').value.trim()) formData.append('notes', field('recNotes').value.trim());
    if (file) formData.append('file', file);

    const submit = field('recSubmit');
    AppUI.setBusy(submit, true, file ? 'Uploading...' : 'Saving...');
    try {
      await SwasthAPI.family.createRecord(formData);
      recDialog.close();
      AppUI.toast('Record saved');
      loadRecords();
    } catch (err) {
      error.textContent = AppUI.errorText(err);
      error.hidden = false;
    } finally {
      AppUI.setBusy(submit, false);
    }
  });

  // Documents need the session token, so they are fetched and handed to the
  // browser as a temporary local URL rather than linked to directly.
  async function openDocument(rec, download) {
    try {
      const blob = await SwasthAPI.family.fetchDocumentBlob(rec.id);
      const url = URL.createObjectURL(blob);
      if (download) {
        const link = document.createElement('a');
        link.href = url;
        link.download = rec.file_name || 'document';
        document.body.appendChild(link);
        link.click();
        link.remove();
      } else {
        window.open(url, '_blank', 'noopener');
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      AppUI.toast('This document could not be opened. Please try again.', 'error');
    }
  }

  recList.addEventListener('click', async (e) => {
    const button = e.target.closest('[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    if (action === 'add') return openRecordForm();
    if (action === 'add-self') {
      AppUI.setBusy(button, true, 'Adding...');
      try {
        await CareProfiles.addSelf();
        state.members = [];
        AppUI.toast('Your profile is ready');
        await loadRecords();
        openRecordForm();
      } catch (err) {
        AppUI.setBusy(button, false);
        AppUI.toast(AppUI.errorText(err), 'error');
      }
      return;
    }
    const rec = state.records.find((r) => r.id === button.closest('[data-id]').dataset.id);
    if (!rec) return;
    if (action === 'open') return openDocument(rec, false);
    if (action === 'download') return openDocument(rec, true);
    if (action === 'delete') {
      const confirmed = await AppUI.confirm({
        title: `Delete "${rec.title}"?`,
        text: rec.has_document
          ? 'The record and its attached document will be deleted permanently. This cannot be undone.'
          : 'This record will be deleted permanently. This cannot be undone.',
        confirmLabel: 'Delete record',
        danger: true
      });
      if (!confirmed) return;
      try {
        await SwasthAPI.family.deleteRecord(rec.id);
        AppUI.toast('Record deleted');
        loadRecords();
      } catch (err) {
        AppUI.toast(AppUI.errorText(err), 'error');
      }
    }
  });

  field('recAddBtn').addEventListener('click', openRecordForm);
  field('recMemberFilter').addEventListener('change', loadRecords);
  field('recCategoryFilter').addEventListener('change', loadRecords);
  let searchTimer;
  field('recSearch').addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadRecords, 300);
  });

  // ── Analysed reports ────────────────────────────────────────────────────
  function reportRow(report) {
    const flagged = report.flagged_count;
    return `
      <li class="row-item" data-id="${AppUI.esc(report.id)}">
        <span class="row-item__icon row-item__icon--teal"><i class="fas fa-file-lines" aria-hidden="true"></i></span>
        <div class="row-item__main">
          <div class="row-item__title">${AppUI.esc(report.filename)}</div>
          <div class="row-item__meta">Analysed ${AppUI.esc(AppUI.fmtDate(report.created_at))} &middot; ${report.values_count} value${report.values_count === 1 ? '' : 's'} recognised</div>
        </div>
        <div class="row-item__aside">
          <span class="pill ${flagged ? 'pill--warn' : 'pill--ok'}">${flagged ? `${flagged} to discuss` : 'All in range'}</span>
          <button type="button" class="btn btn-outline btn-compact" data-action="view">View</button>
          <button type="button" class="icon-btn icon-btn--danger" data-action="delete" aria-label="Delete analysis of ${AppUI.esc(report.filename)}"><i class="fas fa-trash-can" aria-hidden="true"></i></button>
        </div>
      </li>`;
  }

  async function loadReports() {
    reportList.innerHTML = AppUI.skeletonRows(3);
    const pager = field('reportPager');
    try {
      const data = await SwasthAPI.reportAnalysis.history(state.reportPage, REPORT_PAGE_SIZE);
      state.reportsLoaded = true;
      if (!data.items.length && state.reportPage > 1) {
        state.reportPage -= 1;
        return loadReports();
      }
      if (!data.items.length) {
        reportList.innerHTML = AppUI.state({
          icon: 'fa-file-medical',
          title: 'No reports analysed yet',
          text: 'Upload a lab report and SwasthAI will explain each value in plain language and flag what to discuss with your doctor.',
          actionHtml: '<a class="btn btn-primary btn-compact" href="report-analyzer.html">Analyze a report</a>'
        });
        pager.hidden = true;
        return;
      }
      reportList.innerHTML = `<ul class="rows">${data.items.map(reportRow).join('')}</ul>`;
      const first = (state.reportPage - 1) * REPORT_PAGE_SIZE + 1;
      const last = first + data.items.length - 1;
      field('reportCount').textContent = `Showing ${first} to ${last} of ${data.total}`;
      field('reportPrev').disabled = state.reportPage === 1;
      field('reportNext').disabled = last >= data.total;
      pager.hidden = data.total <= REPORT_PAGE_SIZE;
    } catch (err) {
      reportList.innerHTML = AppUI.errorState(AppUI.errorText(err), 'reportRetry');
      pager.hidden = true;
      field('reportRetry')?.addEventListener('click', loadReports);
    }
  }

  const VALUE_STATUS = {
    low: ['Below range', 'pill--warn'],
    high: ['Above range', 'pill--warn'],
    normal: ['In range', 'pill--ok']
  };

  function reportDetailHtml(report) {
    const values = (report.values || []).map((v) => {
      const [label, tone] = VALUE_STATUS[v.status] || ['', ''];
      return `
        <li class="row-item" style="padding-left:0; padding-right:0; align-items:flex-start;">
          <div class="row-item__main">
            <div class="row-item__title">${AppUI.esc(v.label)}</div>
            ${v.description ? `<div class="row-item__meta">${AppUI.esc(v.description)}</div>` : ''}
            <div class="row-item__meta">Reference range: ${AppUI.esc(v.reference_low)} to ${AppUI.esc(v.reference_high)} ${AppUI.esc(v.unit)}</div>
          </div>
          <div class="row-item__aside" style="flex-direction:column; align-items:flex-end;">
            <strong style="font-variant-numeric:tabular-nums;">${AppUI.esc(v.value)} ${AppUI.esc(v.unit)}</strong>
            <span class="pill ${tone}">${label}</span>
          </div>
        </li>`;
    }).join('');

    const screening = (report.qualitative_results || []).map((q) => `
        <li class="row-item" style="padding-left:0; padding-right:0; align-items:flex-start;">
          <div class="row-item__main">
            <div class="row-item__title">${AppUI.esc(q.label)}</div>
            ${q.description ? `<div class="row-item__meta">${AppUI.esc(q.description)}</div>` : ''}
          </div>
          <div class="row-item__aside"><span class="pill ${q.status === 'abnormal' ? 'pill--danger' : 'pill--ok'}">${q.status === 'abnormal' ? 'Reactive / positive' : 'Non-reactive / negative'}</span></div>
        </li>`).join('');

    const questions = (report.questions_to_ask || []).map((q) => `<li>${AppUI.esc(q)}</li>`).join('');

    return `
      <p class="row-item__meta" style="margin:0 0 var(--sp-4);">Analysed ${AppUI.esc(AppUI.fmtDate(report.created_at))}</p>
      <div class="notice" style="margin-bottom: var(--sp-5);"><i class="fas fa-clipboard-list" aria-hidden="true"></i><span>${AppUI.esc(report.summary)}</span></div>
      ${report.llm_explanation ? `<h3 style="font-size:var(--text-base); margin:0 0 var(--sp-2);">In plain language</h3><p style="margin:0 0 var(--sp-5); line-height:1.65; color:var(--text-secondary); white-space:pre-line;">${AppUI.esc(report.llm_explanation)}</p>` : ''}
      ${values ? `<h3 style="font-size:var(--text-base); margin:0;">Values found in the report</h3><ul class="rows" style="margin-bottom: var(--sp-5);">${values}</ul>` : ''}
      ${screening ? `<h3 style="font-size:var(--text-base); margin:0;">Screening tests</h3><ul class="rows" style="margin-bottom: var(--sp-5);">${screening}</ul>` : ''}
      ${questions ? `<h3 style="font-size:var(--text-base); margin:0 0 var(--sp-2);">Questions to ask your doctor</h3><ul class="plain-list" style="margin-bottom: var(--sp-5);">${questions}</ul>` : ''}
      <div class="notice notice--quiet"><i class="fas fa-shield-heart" aria-hidden="true"></i><span>${AppUI.esc(report.disclaimer)}</span></div>`;
  }

  async function viewReport(id) {
    field('reportDialogTitle').textContent = 'Report';
    field('reportDialogBody').innerHTML = AppUI.skeletonRows(3);
    reportDialog.showModal();
    try {
      const report = await SwasthAPI.reportAnalysis.get(id);
      field('reportDialogTitle').textContent = report.filename;
      field('reportDialogBody').innerHTML = reportDetailHtml(report);
    } catch (err) {
      field('reportDialogBody').innerHTML = AppUI.errorState(
        err.status === 404 ? 'This report is no longer available.' : AppUI.errorText(err)
      );
    }
  }

  reportList.addEventListener('click', async (e) => {
    const button = e.target.closest('[data-action]');
    if (!button) return;
    const id = button.closest('[data-id]').dataset.id;
    if (button.dataset.action === 'view') return viewReport(id);
    if (button.dataset.action === 'delete') {
      const confirmed = await AppUI.confirm({
        title: 'Delete this analysis?',
        text: 'The saved values and explanation for this report will be deleted permanently.',
        confirmLabel: 'Delete analysis',
        danger: true
      });
      if (!confirmed) return;
      try {
        await SwasthAPI.reportAnalysis.remove(id);
        AppUI.toast('Analysis deleted');
        loadReports();
      } catch (err) {
        AppUI.toast(AppUI.errorText(err), 'error');
      }
    }
  });
  field('reportPrev').addEventListener('click', () => { state.reportPage -= 1; loadReports(); });
  field('reportNext').addEventListener('click', () => { state.reportPage += 1; loadReports(); });

  document.querySelectorAll('dialog [data-close]').forEach((b) => b.addEventListener('click', () => b.closest('dialog').close()));

  // ── Start ───────────────────────────────────────────────────────────────
  loadRecords();
  const reportParam = new URLSearchParams(window.location.search).get('report');
  if (window.location.hash === '#reports' || reportParam) showTab('reports');
  if (reportParam) viewReport(reportParam);
})();
