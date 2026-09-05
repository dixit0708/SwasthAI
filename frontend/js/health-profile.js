/**
 * SwasthAI — Health Profile page.
 * Loads the current user's real health profile from the backend and
 * wires the Basic Information form and Known Conditions list to it.
 */

function hpShowAlert(message) {
  const alertBox = document.getElementById('hpFormAlert');
  const alertText = document.getElementById('hpFormAlertText');
  if (!alertBox || !alertText) return;
  alertText.textContent = message;
  alertBox.style.display = 'flex';
}

function hpHideAlert() {
  const alertBox = document.getElementById('hpFormAlert');
  if (alertBox) alertBox.style.display = 'none';
}

function hpRenderConditions(conditions) {
  const list = document.getElementById('hpConditionsList');
  const empty = document.getElementById('hpConditionsEmpty');
  if (!list) return;

  list.innerHTML = '';
  empty.style.display = conditions.length ? 'none' : 'block';

  conditions.forEach((condition) => {
    const li = document.createElement('li');
    li.style.cssText = 'display:flex; align-items:center; justify-content:space-between; padding: 0.5rem; background: var(--bg-surface-alt); margin-bottom: 0.5rem; border-radius: var(--radius-sm);';

    const label = document.createElement('span');
    label.innerHTML = '<i class="fas fa-exclamation-triangle text-warning"></i> ';
    label.append(condition.label);

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn btn-outline';
    removeBtn.style.cssText = 'padding: 0.2rem 0.5rem;';
    removeBtn.innerHTML = '<i class="fas fa-times"></i>';
    removeBtn.addEventListener('click', async () => {
      removeBtn.disabled = true;
      try {
        const updated = await SwasthAPI.healthProfile.deleteCondition(condition.id);
        hpRenderConditions(updated.conditions);
      } catch (err) {
        hpShowAlert(err.message);
      }
    });

    li.appendChild(label);
    li.appendChild(removeBtn);
    list.appendChild(li);
  });
}

async function hpLoadProfile() {
  try {
    const profile = await SwasthAPI.healthProfile.get();
    const dobEl = document.getElementById('hpDob');
    const bgEl = document.getElementById('hpBloodGroup');
    if (dobEl) dobEl.value = profile.date_of_birth || '';
    if (bgEl) bgEl.value = profile.blood_group || '';
    hpRenderConditions(profile.conditions || []);
  } catch (err) {
    hpShowAlert(err.message);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const user = typeof swasthaiCurrentUser === 'function' && swasthaiCurrentUser();
  if (user && user.name) {
    const parts = user.name.trim().split(/\s+/);
    const firstEl = document.getElementById('hpFirstName');
    const lastEl = document.getElementById('hpLastName');
    if (firstEl) firstEl.value = parts[0] || '';
    if (lastEl) lastEl.value = parts.slice(1).join(' ');
  }

  if (!document.getElementById('hpForm')) return;

  hpLoadProfile();

  document.getElementById('hpForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    hpHideAlert();
    const saveBtn = document.getElementById('hpSaveBtn');
    const originalText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    try {
      await SwasthAPI.healthProfile.update({
        date_of_birth: document.getElementById('hpDob').value,
        blood_group: document.getElementById('hpBloodGroup').value
      });
      saveBtn.textContent = 'Saved!';
      setTimeout(() => { saveBtn.textContent = originalText; }, 1500);
    } catch (err) {
      hpShowAlert(err.message);
      saveBtn.textContent = originalText;
    } finally {
      saveBtn.disabled = false;
    }
  });

  document.getElementById('hpAddConditionBtn').addEventListener('click', async () => {
    const label = window.prompt('Add a condition or allergy (e.g. "Peanut Allergy"):');
    if (!label || !label.trim()) return;
    try {
      const updated = await SwasthAPI.healthProfile.addCondition(label.trim());
      hpRenderConditions(updated.conditions);
    } catch (err) {
      hpShowAlert(err.message);
    }
  });
});
