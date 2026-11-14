/**
 * SwasthAI — My appointments.
 * Lists the user's scheduled visits (GET /appointments) and lets them
 * confirm, reschedule, complete, cancel or remove each one.
 */
(() => {
  const PAGE_SIZE = 8;
  const state = { view: 'upcoming', page: 1, items: [] };

  const list = document.getElementById('apptList');
  const pager = document.getElementById('apptPager');
  const count = document.getElementById('apptCount');
  const prev = document.getElementById('apptPrev');
  const next = document.getElementById('apptNext');
  if (!list) return;

  const STATUS = {
    scheduled: { label: 'Confirm with clinic', tone: 'pill--warn' },
    confirmed: { label: 'Confirmed', tone: 'pill--ok' },
    completed: { label: 'Completed', tone: 'pill--info' },
    cancelled: { label: 'Cancelled', tone: '' }
  };

  function statusPill(appt) {
    // An active visit whose date has passed was never marked either way.
    if (!appt.is_upcoming && (appt.status === 'scheduled' || appt.status === 'confirmed')) {
      return '<span class="pill">Date passed</span>';
    }
    const info = STATUS[appt.status] || STATUS.scheduled;
    return `<span class="pill ${info.tone}">${info.label}</span>`;
  }

  function actionsHtml(appt) {
    const buttons = [];
    if (appt.is_upcoming) {
      if (appt.status === 'scheduled') {
        buttons.push('<button type="button" class="btn btn-primary btn-compact" data-action="confirm">Mark confirmed</button>');
      }
      buttons.push('<button type="button" class="btn btn-outline btn-compact" data-action="reschedule">Reschedule</button>');
      buttons.push('<button type="button" class="btn btn-danger-outline btn-compact" data-action="cancel">Cancel</button>');
    } else {
      if (appt.status === 'scheduled' || appt.status === 'confirmed') {
        buttons.push('<button type="button" class="btn btn-outline btn-compact" data-action="complete">Mark as attended</button>');
      }
      buttons.push('<button type="button" class="icon-btn icon-btn--danger" data-action="remove" aria-label="Remove this appointment from your list"><i class="fas fa-trash-can" aria-hidden="true"></i></button>');
    }
    return buttons.join('');
  }

  function rowHtml(appt) {
    const where = [appt.clinic_name, appt.address, appt.city].filter(Boolean).filter((v, i, all) => all.indexOf(v) === i).join(', ');
    const contact = [];
    if (appt.phone) contact.push(`<a href="tel:${AppUI.esc(appt.phone_dial || '')}"><i class="fas fa-phone" aria-hidden="true"></i> ${AppUI.esc(appt.phone)}</a>`);
    if (appt.directions_url) contact.push(`<a href="${AppUI.esc(appt.directions_url)}" target="_blank" rel="noopener noreferrer"><i class="fas fa-diamond-turn-right" aria-hidden="true"></i> Directions<span class="visually-hidden"> (opens in a new tab)</span></a>`);
    contact.push(`<a href="doctor-profile.html?id=${encodeURIComponent(appt.doctor_id)}"><i class="fas fa-hospital-user" aria-hidden="true"></i> View listing</a>`);

    return `
      <li class="row-item" data-id="${AppUI.esc(appt.id)}" style="align-items:flex-start;">
        <span class="row-item__icon row-item__icon--blue" style="flex-direction:column; width:56px; height:56px; line-height:1.1;">
          <strong style="font-size:1.1rem;">${AppUI.esc(AppUI.fmtDate(appt.appointment_date, { day: 'numeric' }))}</strong>
          <span style="font-size:0.7rem; text-transform:uppercase; letter-spacing:0.04em;">${AppUI.esc(AppUI.fmtDate(appt.appointment_date, { month: 'short' }))}</span>
        </span>
        <div class="row-item__main">
          <div class="row-item__title">${AppUI.esc(appt.doctor_name)}</div>
          <div class="row-item__meta">
            ${AppUI.esc(AppUI.fmtDate(appt.appointment_date, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }))} at ${AppUI.esc(AppUI.fmtTime(appt.appointment_time))}
            ${appt.is_upcoming ? ` &middot; ${AppUI.esc(AppUI.relativeDay(appt.appointment_date))}` : ''}
          </div>
          ${where ? `<div class="row-item__meta"><i class="fas fa-location-dot" aria-hidden="true"></i> ${AppUI.esc(where)}</div>` : ''}
          ${appt.patient_name ? `<div class="row-item__meta"><i class="fas fa-user" aria-hidden="true"></i> For ${AppUI.esc(appt.patient_name)}</div>` : ''}
          ${appt.reason ? `<div class="row-item__meta"><i class="fas fa-note-sticky" aria-hidden="true"></i> ${AppUI.esc(appt.reason)}</div>` : ''}
          <div class="row-item__meta" style="display:flex; gap: var(--sp-4); flex-wrap:wrap; margin-top: var(--sp-2);">${contact.join('')}</div>
        </div>
        <div class="row-item__aside" style="flex-direction:column; align-items:flex-end; gap: var(--sp-3);">
          ${statusPill(appt)}
          <div style="display:flex; gap: var(--sp-2); flex-wrap:wrap; justify-content:flex-end;">${actionsHtml(appt)}</div>
        </div>
      </li>`;
  }

  async function load() {
    list.innerHTML = AppUI.skeletonRows(3);
    try {
      const data = await SwasthAPI.appointments.list(state.view, state.page, PAGE_SIZE);
      if (!data.items.length && state.page > 1) {
        state.page -= 1;
        return load();
      }
      state.items = data.items;
      if (!data.items.length) {
        list.innerHTML = state.view === 'upcoming'
          ? AppUI.state({
              icon: 'fa-calendar-plus',
              title: 'No upcoming appointments',
              text: 'Find a doctor or clinic, choose a date and time, and your visit will appear here.',
              actionHtml: '<a class="btn btn-primary btn-compact" href="doctors.html">Find a doctor</a>'
            })
          : AppUI.state({
              icon: 'fa-clock-rotate-left',
              title: 'No past appointments',
              text: 'Visits you have attended or cancelled will be listed here.'
            });
        pager.hidden = true;
        return;
      }
      list.innerHTML = `<ul class="rows">${data.items.map(rowHtml).join('')}</ul>`;
      const first = (state.page - 1) * PAGE_SIZE + 1;
      const last = first + data.items.length - 1;
      count.textContent = `Showing ${first} to ${last} of ${data.total}`;
      prev.disabled = state.page === 1;
      next.disabled = last >= data.total;
      pager.hidden = data.total <= PAGE_SIZE;
    } catch (err) {
      list.innerHTML = AppUI.errorState(AppUI.errorText(err), 'apptRetry');
      pager.hidden = true;
      document.getElementById('apptRetry')?.addEventListener('click', load);
    }
  }

  async function changeStatus(id, status, successMessage) {
    try {
      await SwasthAPI.appointments.update(id, { status });
      AppUI.toast(successMessage);
      load();
    } catch (err) {
      AppUI.toast(AppUI.errorText(err), 'error');
    }
  }

  list.addEventListener('click', async (e) => {
    const button = e.target.closest('[data-action]');
    if (!button) return;
    const id = button.closest('[data-id]').dataset.id;
    const appt = state.items.find((a) => a.id === id);
    if (!appt) return;

    switch (button.dataset.action) {
      case 'confirm':
        if (await AppUI.confirm({
          title: 'Has the clinic confirmed this slot?',
          text: `Mark this only after you have spoken to ${appt.doctor_name} and they have agreed to the date and time.`,
          confirmLabel: 'Yes, it is confirmed'
        })) changeStatus(id, 'confirmed', 'Marked as confirmed');
        break;
      case 'reschedule':
        AppointmentForm.open({
          appointment: appt,
          onSaved: () => { AppUI.toast('Visit rescheduled. Please confirm the new time with the clinic.'); load(); }
        });
        break;
      case 'cancel':
        if (await AppUI.confirm({
          title: 'Cancel this appointment?',
          text: 'This updates your SwasthAI schedule only. If the clinic is expecting you, please let them know too.',
          confirmLabel: 'Cancel appointment',
          danger: true
        })) changeStatus(id, 'cancelled', 'Appointment cancelled');
        break;
      case 'complete':
        changeStatus(id, 'completed', 'Marked as attended');
        break;
      case 'remove':
        if (await AppUI.confirm({
          title: 'Remove this appointment?',
          text: 'It will be deleted from your list permanently.',
          confirmLabel: 'Remove',
          danger: true
        })) {
          try {
            await SwasthAPI.appointments.remove(id);
            AppUI.toast('Appointment removed');
            load();
          } catch (err) {
            AppUI.toast(AppUI.errorText(err), 'error');
          }
        }
        break;
      default:
    }
  });

  document.querySelectorAll('.tabs__btn[data-view]').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.tabs__btn[data-view]').forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
      state.view = button.dataset.view;
      state.page = 1;
      load();
    });
  });
  prev.addEventListener('click', () => { state.page -= 1; load(); });
  next.addEventListener('click', () => { state.page += 1; load(); });

  load();
})();
