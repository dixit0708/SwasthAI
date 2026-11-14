/**
 * SwasthAI — Medications.
 * A list of the medicines recorded for the account holder and their
 * family, with add, edit, status change and delete. Uses the
 * /family/medications API; every medicine belongs to a profile.
 */
(() => {
  const list = document.getElementById('medList');
  const dialog = document.getElementById('medDialog');
  const form = document.getElementById('medForm');
  const memberFilter = document.getElementById('medMemberFilter');
  const addBtn = document.getElementById('medAddBtn');
  if (!list || !dialog) return;

  const field = (id) => document.getElementById(id);
  const state = { status: 'active', memberId: '', members: [], items: [], editingId: null };

  const STATUS = {
    active: { label: 'Currently taking', tone: 'pill--ok' },
    completed: { label: 'Course completed', tone: 'pill--info' },
    paused: { label: 'Paused or stopped', tone: 'pill--warn' }
  };

  function rowHtml(med) {
    const info = STATUS[med.status] || { label: med.status, tone: '' };
    const dates = [
      med.start_date ? `Started ${AppUI.fmtDate(med.start_date)}` : '',
      med.end_date ? `Until ${AppUI.fmtDate(med.end_date)}` : ''
    ].filter(Boolean).join(' · ');
    return `
      <li class="row-item" data-id="${AppUI.esc(med.id)}" style="align-items:flex-start;">
        <span class="row-item__icon row-item__icon--teal"><i class="fas fa-pills" aria-hidden="true"></i></span>
        <div class="row-item__main">
          <div class="row-item__title">${AppUI.esc(med.name)} <span style="font-weight:500; color:var(--text-secondary);">&middot; ${AppUI.esc(med.dosage)}</span></div>
          <div class="row-item__meta"><i class="fas fa-clock" aria-hidden="true"></i> ${AppUI.esc(med.frequency)}${med.instructions ? ` &middot; ${AppUI.esc(med.instructions)}` : ''}</div>
          <div class="row-item__meta"><i class="fas fa-user" aria-hidden="true"></i> ${AppUI.esc(med.member_name || 'Profile')}${med.prescribing_doctor ? ` &middot; Prescribed by ${AppUI.esc(med.prescribing_doctor)}` : ''}</div>
          ${dates ? `<div class="row-item__meta">${AppUI.esc(dates)}</div>` : ''}
        </div>
        <div class="row-item__aside">
          <span class="pill ${info.tone}">${AppUI.esc(info.label)}</span>
          <button type="button" class="icon-btn" data-action="edit" aria-label="Edit ${AppUI.esc(med.name)}"><i class="fas fa-pen" aria-hidden="true"></i></button>
          <button type="button" class="icon-btn icon-btn--danger" data-action="delete" aria-label="Delete ${AppUI.esc(med.name)}"><i class="fas fa-trash-can" aria-hidden="true"></i></button>
        </div>
      </li>`;
  }

  function render() {
    const visible = state.items.filter((m) => (state.status === 'active' ? m.status === 'active' : m.status !== 'active'));
    if (!visible.length) {
      list.innerHTML = state.status === 'active'
        ? AppUI.state({
            icon: 'fa-pills',
            title: 'No current medications',
            text: 'Add the medicines you take so you always have an accurate list for your doctor or pharmacist.',
            actionHtml: '<button type="button" class="btn btn-primary btn-compact" data-action="add">Add medication</button>'
          })
        : AppUI.state({
            icon: 'fa-clock-rotate-left',
            title: 'No past medications',
            text: 'Medicines you have finished or stopped will be kept here for reference.'
          });
      return;
    }
    list.innerHTML = `<ul class="rows">${visible.map(rowHtml).join('')}</ul>`;
  }

  async function load() {
    list.innerHTML = AppUI.skeletonRows(3);
    try {
      state.members = await CareProfiles.list();
      memberFilter.innerHTML = `<option value="">Everyone</option>${CareProfiles.optionsHtml(state.members, state.memberId)}`;
      memberFilter.hidden = state.members.length < 2;

      if (!state.members.length) {
        list.innerHTML = CareProfiles.emptyStateHtml('Medicines');
        return;
      }
      state.items = await SwasthAPI.family.listMedications({ memberId: state.memberId });
      render();
    } catch (err) {
      list.innerHTML = AppUI.errorState(AppUI.errorText(err), 'medRetry');
      document.getElementById('medRetry')?.addEventListener('click', load);
    }
  }

  function openForm(med) {
    if (!state.members.length) {
      AppUI.toast('Add a profile first, then you can add medicines.', 'error');
      return;
    }
    state.editingId = med ? med.id : null;
    field('medDialogTitle').textContent = med ? 'Edit medication' : 'Add medication';
    field('medSubmit').textContent = med ? 'Save changes' : 'Save medication';
    field('medMember').innerHTML = CareProfiles.optionsHtml(state.members, med ? med.member_id : (state.memberId || state.members[0].id));
    // A medicine stays with the person it was recorded for.
    field('medMember').disabled = Boolean(med);
    field('medName').value = med ? med.name : '';
    field('medDosage').value = med ? med.dosage : '';
    field('medFrequency').value = med ? med.frequency : '';
    field('medInstructions').value = (med && med.instructions) || '';
    field('medDoctor').value = (med && med.prescribing_doctor) || '';
    field('medStart').value = (med && med.start_date) || '';
    field('medEnd').value = (med && med.end_date) || '';
    field('medStatus').value = med ? med.status : 'active';
    field('medFormError').hidden = true;
    dialog.showModal();
    field('medName').focus();
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const error = field('medFormError');
    error.hidden = true;

    const name = field('medName').value.trim();
    const dosage = field('medDosage').value.trim();
    const frequency = field('medFrequency').value.trim();
    const start = field('medStart').value;
    const end = field('medEnd').value;
    let problem = '';
    if (!name) problem = 'Please enter the medicine name.';
    else if (!dosage) problem = 'Please enter the dose.';
    else if (!frequency) problem = 'Please enter how often it is taken.';
    else if (start && end && end < start) problem = 'The end date cannot be before the start date.';
    if (problem) {
      error.textContent = problem;
      error.hidden = false;
      return;
    }

    const payload = {
      name,
      dosage,
      frequency,
      instructions: field('medInstructions').value.trim() || null,
      prescribing_doctor: field('medDoctor').value.trim() || null,
      start_date: start || null,
      end_date: end || null,
      status: field('medStatus').value
    };

    const submit = field('medSubmit');
    AppUI.setBusy(submit, true, 'Saving...');
    try {
      if (state.editingId) {
        await SwasthAPI.family.updateMedication(state.editingId, payload);
      } else {
        await SwasthAPI.family.createMedication({ ...payload, member_id: field('medMember').value });
      }
      dialog.close();
      AppUI.toast(state.editingId ? 'Medication updated' : 'Medication added');
      load();
    } catch (err) {
      error.textContent = AppUI.errorText(err);
      error.hidden = false;
    } finally {
      AppUI.setBusy(submit, false);
    }
  });

  dialog.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => dialog.close()));
  addBtn.addEventListener('click', () => openForm(null));

  list.addEventListener('click', async (e) => {
    const button = e.target.closest('[data-action]');
    if (!button) return;
    const action = button.dataset.action;

    if (action === 'add') return openForm(null);
    if (action === 'add-self') {
      AppUI.setBusy(button, true, 'Adding...');
      try {
        await CareProfiles.addSelf();
        AppUI.toast('Your profile is ready');
        await load();
        openForm(null);
      } catch (err) {
        AppUI.setBusy(button, false);
        AppUI.toast(AppUI.errorText(err), 'error');
      }
      return;
    }

    const id = button.closest('[data-id]').dataset.id;
    const med = state.items.find((m) => m.id === id);
    if (!med) return;
    if (action === 'edit') return openForm(med);
    if (action === 'delete') {
      const confirmed = await AppUI.confirm({
        title: `Delete ${med.name}?`,
        text: 'This removes it from the list permanently. To keep it for reference, edit it and mark it as completed or stopped instead.',
        confirmLabel: 'Delete',
        danger: true
      });
      if (!confirmed) return;
      try {
        await SwasthAPI.family.deleteMedication(id);
        AppUI.toast('Medication deleted');
        load();
      } catch (err) {
        AppUI.toast(AppUI.errorText(err), 'error');
      }
    }
  });

  document.querySelectorAll('.tabs__btn[data-status]').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.tabs__btn[data-status]').forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
      state.status = button.dataset.status;
      render();
    });
  });
  memberFilter.addEventListener('change', () => {
    state.memberId = memberFilter.value;
    load();
  });

  load();
})();
