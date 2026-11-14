/**
 * SwasthAI — Health profile.
 * Loads and saves the signed-in user's profile: body measurements,
 * lifestyle, health conditions and allergies. Also hosts the change
 * password form.
 */
(() => {
  const form = document.getElementById('hpForm');
  if (!form) return;
  const field = (id) => document.getElementById(id);
  let allergies = [];

  // ── BMI preview (the saved value is always recomputed by the server) ────
  const BMI_BANDS = [
    [18.5, 'Below the healthy range', 'pill--warn'],
    [25, 'Healthy range', 'pill--ok'],
    [30, 'Above the healthy range', 'pill--warn'],
    [Infinity, 'Well above the healthy range', 'pill--danger']
  ];

  function renderBmi() {
    const height = parseFloat(field('hpHeight').value);
    const weight = parseFloat(field('hpWeight').value);
    const box = field('hpBmi');
    if (!height || !weight || height < 30 || weight < 1) {
      box.textContent = 'Add height and weight';
      return;
    }
    const bmi = weight / ((height / 100) ** 2);
    const [, label, tone] = BMI_BANDS.find(([limit]) => bmi < limit);
    box.innerHTML = `<strong style="font-variant-numeric:tabular-nums;">${bmi.toFixed(1)}</strong><span class="pill ${tone}">${label}</span>`;
  }

  // ── Chips ───────────────────────────────────────────────────────────────
  function chipHtml(label, attr, value) {
    return `<li class="chip">${AppUI.esc(label)}<button type="button" class="chip__remove" ${attr}="${AppUI.esc(value)}" aria-label="Remove ${AppUI.esc(label)}"><i class="fas fa-xmark" aria-hidden="true"></i></button></li>`;
  }

  function renderConditions(conditions) {
    field('hpConditionsList').innerHTML = conditions.map((c) => chipHtml(c.label, 'data-condition', c.id)).join('');
    field('hpConditionsEmpty').hidden = conditions.length > 0;
  }

  function renderAllergies() {
    field('hpAllergiesList').innerHTML = allergies.map((a) => chipHtml(a, 'data-allergy', a)).join('');
    field('hpAllergiesEmpty').hidden = allergies.length > 0;
  }

  function fill(profile) {
    field('hpDob').value = profile.date_of_birth || '';
    field('hpGender').value = profile.gender || '';
    field('hpHeight').value = profile.height_cm ?? '';
    field('hpWeight').value = profile.weight_kg ?? '';
    field('hpBloodGroup').value = profile.blood_group || '';
    field('hpActivity').value = profile.activity_level || '';
    field('hpDiet').value = profile.diet_preference || '';
    field('hpSmoking').value = profile.smoking_status || '';
    field('hpAlcohol').value = profile.alcohol_use || '';
    field('hpSleep').value = profile.sleep_hours ?? '';
    field('hpOccupation').value = profile.occupation_type || '';
    field('hpRegion').value = profile.cuisine_region || '';
    allergies = profile.allergies || [];
    renderBmi();
    renderAllergies();
    renderConditions(profile.conditions || []);
  }

  function setStatus(id, message, type) {
    const el = field(id);
    el.textContent = message;
    el.className = `form-status${type ? ` form-status--${type}` : ''}`;
  }

  async function load() {
    const errorBox = field('hpLoadError');
    try {
      fill(await SwasthAPI.healthProfile.get());
      errorBox.hidden = true;
      field('hpContent').hidden = false;
    } catch (err) {
      field('hpContent').hidden = true;
      errorBox.hidden = false;
      errorBox.innerHTML = `<div class="panel">${AppUI.errorState(AppUI.errorText(err), 'hpRetry')}</div>`;
      field('hpRetry')?.addEventListener('click', load);
    }
  }

  // ── Save profile ────────────────────────────────────────────────────────
  function numberOrNull(id) {
    const raw = field(id).value.trim();
    return raw === '' ? null : Number(raw);
  }

  function validate() {
    const height = numberOrNull('hpHeight');
    const weight = numberOrNull('hpWeight');
    const sleep = numberOrNull('hpSleep');
    const dob = field('hpDob').value;
    if (dob && dob > AppUI.todayIso()) return 'Date of birth cannot be in the future.';
    if (height !== null && (Number.isNaN(height) || height < 30 || height > 260)) return 'Please enter your height in centimetres (30 to 260).';
    if (weight !== null && (Number.isNaN(weight) || weight < 1 || weight > 400)) return 'Please enter your weight in kilograms (1 to 400).';
    if (sleep !== null && (Number.isNaN(sleep) || sleep < 0 || sleep > 24)) return 'Sleep must be between 0 and 24 hours.';
    return '';
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const problem = validate();
    if (problem) return setStatus('hpFormStatus', problem, 'error');

    const button = field('hpSaveBtn');
    setStatus('hpFormStatus', '');
    AppUI.setBusy(button, true, 'Saving...');
    try {
      fill(await SwasthAPI.healthProfile.update({
        date_of_birth: field('hpDob').value || null,
        gender: field('hpGender').value || null,
        height_cm: numberOrNull('hpHeight'),
        weight_kg: numberOrNull('hpWeight'),
        blood_group: field('hpBloodGroup').value || null,
        activity_level: field('hpActivity').value || null,
        diet_preference: field('hpDiet').value || null,
        smoking_status: field('hpSmoking').value || null,
        alcohol_use: field('hpAlcohol').value || null,
        sleep_hours: numberOrNull('hpSleep'),
        occupation_type: field('hpOccupation').value || null,
        cuisine_region: field('hpRegion').value || null
      }));
      setStatus('hpFormStatus', 'Profile saved', 'ok');
      AppUI.toast('Profile saved. Your diet and activity plan has been updated.');
    } catch (err) {
      setStatus('hpFormStatus', AppUI.errorText(err), 'error');
    } finally {
      AppUI.setBusy(button, false);
    }
  });
  ['hpHeight', 'hpWeight'].forEach((id) => field(id).addEventListener('input', renderBmi));

  // ── Conditions ──────────────────────────────────────────────────────────
  field('hpConditionForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = field('hpConditionInput');
    const label = input.value.trim();
    if (!label) return;
    try {
      const updated = await SwasthAPI.healthProfile.addCondition(label);
      renderConditions(updated.conditions);
      input.value = '';
      input.focus();
    } catch (err) {
      AppUI.toast(AppUI.errorText(err), 'error');
    }
  });

  field('hpConditionsList').addEventListener('click', async (e) => {
    const button = e.target.closest('[data-condition]');
    if (!button) return;
    button.disabled = true;
    try {
      const updated = await SwasthAPI.healthProfile.deleteCondition(button.dataset.condition);
      renderConditions(updated.conditions);
    } catch (err) {
      button.disabled = false;
      AppUI.toast(AppUI.errorText(err), 'error');
    }
  });

  // ── Allergies (saved straight away, like conditions) ────────────────────
  async function saveAllergies(next) {
    try {
      const updated = await SwasthAPI.healthProfile.update({ allergies: next });
      allergies = updated.allergies || [];
      renderAllergies();
      return true;
    } catch (err) {
      AppUI.toast(AppUI.errorText(err), 'error');
      return false;
    }
  }

  field('hpAllergyForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = field('hpAllergyInput');
    const label = input.value.trim();
    if (!label) return;
    if (allergies.some((a) => a.toLowerCase() === label.toLowerCase())) {
      input.value = '';
      return;
    }
    if (await saveAllergies([...allergies, label])) {
      input.value = '';
      input.focus();
    }
  });

  field('hpAllergiesList').addEventListener('click', (e) => {
    const button = e.target.closest('[data-allergy]');
    if (!button) return;
    saveAllergies(allergies.filter((a) => a !== button.dataset.allergy));
  });

  // ── Account ─────────────────────────────────────────────────────────────
  const user = typeof swasthaiCurrentUser === 'function' ? swasthaiCurrentUser() : null;
  field('hpAccountName').textContent = (user && user.name) || '';
  field('hpAccountEmail').textContent = (user && user.email) || '';

  field('hpPasswordForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const current = field('hpCurrentPassword').value;
    const next = field('hpNewPassword').value;
    const confirm = field('hpConfirmPassword').value;

    if (!current || !next) return setStatus('hpPasswordStatus', 'Please fill in all three fields.', 'error');
    if (next !== confirm) return setStatus('hpPasswordStatus', 'The new passwords do not match.', 'error');
    if (next === current) return setStatus('hpPasswordStatus', 'Please choose a password different from your current one.', 'error');

    const button = field('hpPasswordBtn');
    setStatus('hpPasswordStatus', '');
    AppUI.setBusy(button, true, 'Updating...');
    try {
      const session = await SwasthAPI.changePassword(current, next);
      // Keep this device signed in with the fresh token.
      if (typeof swasthaiStoreSession === 'function') swasthaiStoreSession(session);
      field('hpPasswordForm').reset();
      setStatus('hpPasswordStatus', 'Password updated', 'ok');
      AppUI.toast('Password updated. Other devices have been signed out.');
    } catch (err) {
      setStatus('hpPasswordStatus', AppUI.errorText(err), 'error');
    } finally {
      AppUI.setBusy(button, false);
    }
  });

  load();
})();
