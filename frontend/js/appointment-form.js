/**
 * SwasthAI — "Schedule a visit" / "Reschedule" dialog.
 * Shared by the doctor details page (new appointment) and the
 * appointments page (reschedule).
 *
 * SwasthAI does not contact the clinic. The dialog says so plainly, and a
 * saved appointment starts as "Confirm with clinic" until the user marks
 * it confirmed.
 */
const AppointmentForm = (() => {
  let dialog;

  function build() {
    dialog = document.createElement('dialog');
    dialog.className = 'sheet';
    dialog.setAttribute('aria-labelledby', 'apptFormTitle');
    dialog.innerHTML = `
      <form id="apptForm" novalidate style="display:flex; flex-direction:column; min-height:0;">
        <div class="sheet__head">
          <h2 id="apptFormTitle">Schedule a visit</h2>
          <button type="button" class="icon-btn" id="apptFormClose" aria-label="Close"><i class="fas fa-xmark" aria-hidden="true"></i></button>
        </div>
        <div class="sheet__body" data-lenis-prevent>
          <p id="apptFormDoctor" style="margin:0 0 var(--sp-4); font-weight:600;"></p>
          <div class="notice notice--warn" id="apptFormNotice" style="margin-bottom: var(--sp-5);"></div>
          <div class="form-grid">
            <label class="field">
              <span class="field__label">Date</span>
              <input type="date" class="field__control" id="apptDate" required>
            </label>
            <label class="field">
              <span class="field__label">Time</span>
              <input type="time" class="field__control" id="apptTime" step="300" required>
            </label>
            <label class="field field--full" id="apptForField">
              <span class="field__label">Who is this visit for?</span>
              <select class="field__control" id="apptFor"><option value="">Myself</option></select>
            </label>
            <label class="field field--full" id="apptReasonField">
              <span class="field__label">Reason for visit <small>(optional)</small></span>
              <textarea class="field__control" id="apptReason" maxlength="300" placeholder="For example: follow-up on blood sugar results"></textarea>
              <span class="field__hint">Only you can see this. It is not sent to the clinic.</span>
            </label>
          </div>
          <p class="form-status form-status--error" id="apptFormError" role="alert" style="margin: var(--sp-4) 0 0;" hidden></p>
        </div>
        <div class="sheet__foot">
          <button type="button" class="btn btn-outline btn-compact" id="apptFormCancel">Cancel</button>
          <button type="submit" class="btn btn-primary btn-compact" id="apptFormSubmit">Add to my appointments</button>
        </div>
      </form>`;
    document.body.appendChild(dialog);
    dialog.querySelector('#apptFormClose').addEventListener('click', () => dialog.close());
    dialog.querySelector('#apptFormCancel').addEventListener('click', () => dialog.close());
  }

  function noticeHtml(doctor) {
    const call = doctor.phone
      ? `Call <a href="tel:${AppUI.esc(doctor.phone_dial || '')}">${AppUI.esc(doctor.phone)}</a> to confirm your slot.`
      : 'Contact the clinic directly to confirm your slot.';
    const timings = doctor.timings ? ` Consultation timings: <strong>${AppUI.esc(doctor.timings)}</strong>.` : '';
    return `<i class="fas fa-phone-volume" aria-hidden="true"></i><span><strong>SwasthAI does not book with the clinic for you.</strong> This adds the visit to your own schedule. ${call}${timings}</span>`;
  }

  async function loadFamily(select) {
    try {
      const members = await SwasthAPI.family.listMembers();
      members
        .filter((m) => (m.relationship || '').toLowerCase() !== 'self')
        .forEach((m) => {
          const option = document.createElement('option');
          option.value = m.id;
          option.textContent = `${m.name} (${m.relationship})`;
          select.appendChild(option);
        });
    } catch (err) {
      // The visit can still be scheduled for the user themself.
    }
  }

  /**
   * open({ doctor, onSaved })               -> schedule a new visit
   * open({ appointment, onSaved })          -> reschedule an existing one
   * `doctor` needs: id, name, phone, phone_dial, timings.
   */
  function open({ doctor, appointment, onSaved }) {
    if (!dialog) build();
    const form = dialog.querySelector('#apptForm');
    const date = dialog.querySelector('#apptDate');
    const time = dialog.querySelector('#apptTime');
    const reason = dialog.querySelector('#apptReason');
    const forSelect = dialog.querySelector('#apptFor');
    const error = dialog.querySelector('#apptFormError');
    const submit = dialog.querySelector('#apptFormSubmit');
    const isReschedule = Boolean(appointment);
    const place = isReschedule
      ? { name: appointment.doctor_name, phone: appointment.phone, phone_dial: appointment.phone_dial, timings: appointment.timings }
      : doctor;

    dialog.querySelector('#apptFormTitle').textContent = isReschedule ? 'Reschedule visit' : 'Schedule a visit';
    dialog.querySelector('#apptFormDoctor').textContent = place.name;
    dialog.querySelector('#apptFormNotice').innerHTML = noticeHtml(place);
    dialog.querySelector('#apptForField').hidden = isReschedule;
    dialog.querySelector('#apptReasonField').hidden = isReschedule;
    submit.textContent = isReschedule ? 'Save new time' : 'Add to my appointments';
    error.hidden = true;

    date.min = AppUI.todayIso();
    date.value = isReschedule ? appointment.appointment_date : '';
    time.value = isReschedule ? appointment.appointment_time : '';
    reason.value = '';
    forSelect.length = 1;
    if (!isReschedule) loadFamily(forSelect);

    form.onsubmit = async (e) => {
      e.preventDefault();
      error.hidden = true;
      if (!date.value || !time.value) {
        error.textContent = 'Please choose both a date and a time.';
        error.hidden = false;
        return;
      }
      if (date.value < AppUI.todayIso()) {
        error.textContent = 'Please choose today or a later date.';
        error.hidden = false;
        return;
      }
      AppUI.setBusy(submit, true, 'Saving...');
      try {
        const saved = isReschedule
          ? await SwasthAPI.appointments.update(appointment.id, {
              appointment_date: date.value,
              appointment_time: time.value
            })
          : await SwasthAPI.appointments.create({
              doctor_id: doctor.id,
              appointment_date: date.value,
              appointment_time: time.value,
              reason: reason.value.trim() || null,
              family_member_id: forSelect.value || null
            });
        dialog.close();
        if (onSaved) onSaved(saved);
      } catch (err) {
        error.textContent = AppUI.errorText(err);
        error.hidden = false;
      } finally {
        AppUI.setBusy(submit, false);
        submit.textContent = isReschedule ? 'Save new time' : 'Add to my appointments';
      }
    };

    dialog.showModal();
    date.focus();
  }

  return { open };
})();
