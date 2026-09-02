/**
 * SwasthAI — Doctors directory (demo/fictional data, client-side search & filter)
 */
const SWASTHAI_DOCTORS = [
  { name: 'Dr. Sarah Mitchell', specialty: 'Cardiologist', specialtyKey: 'cardiology', experience: 15, location: 'New York, NY', modes: ['video', 'in-person'], availability: 'today', color: '0F766E' },
  { name: 'Dr. Alan Chen', specialty: 'Endocrinologist', specialtyKey: 'endocrinology', experience: 8, location: 'Online Only', modes: ['video'], availability: 'week', color: '0284C7' },
  { name: 'Dr. Priya Mehta', specialty: 'Dermatologist', specialtyKey: 'dermatology', experience: 12, location: 'San Francisco, CA', modes: ['in-person'], availability: 'busy', color: '7C3AED' },
  { name: 'Dr. James Carter', specialty: 'General Physician', specialtyKey: 'general', experience: 6, location: 'Chicago, IL', modes: ['video', 'in-person'], availability: 'today', color: 'D97706' },
  { name: 'Dr. Meera Nair', specialty: 'Pediatrician', specialtyKey: 'pediatrics', experience: 10, location: 'Austin, TX', modes: ['in-person'], availability: 'week', color: 'DC2626' },
  { name: 'Dr. Robert Kim', specialty: 'Neurologist', specialtyKey: 'neurology', experience: 18, location: 'Boston, MA', modes: ['video'], availability: 'busy', color: '059669' },
  { name: 'Dr. Lisa Fernandez', specialty: 'Cardiologist', specialtyKey: 'cardiology', experience: 9, location: 'Miami, FL', modes: ['video', 'in-person'], availability: 'today', color: '0F766E' },
  { name: 'Dr. Omar Hassan', specialty: 'Endocrinologist', specialtyKey: 'endocrinology', experience: 14, location: 'Online Only', modes: ['video'], availability: 'week', color: '0284C7' }
];

const AVAILABILITY_LABEL = {
  today: { text: 'Available Today', cls: 'badge-success' },
  week: { text: 'Available This Week', cls: 'badge-info' },
  busy: { text: 'Fully Booked', cls: 'badge-warning' }
};

function swasthaiDoctorRow(doc) {
  const avail = AVAILABILITY_LABEL[doc.availability];
  const modeLabel = doc.modes.map(m => m === 'video' ? '<span><i class="fas fa-video"></i> Video</span>' : '<span><i class="fas fa-hospital"></i> In-Person</span>').join('');
  return `
    <div class="doctor-row">
        <div class="doctor-row__avatar"><img src="https://ui-avatars.com/api/?name=${encodeURIComponent(doc.name)}&background=${doc.color}&color=fff&size=64" alt="${doc.name}"></div>
        <div>
            <div class="doctor-row__name">${doc.name} <i class="fas fa-circle-check" title="Verified"></i></div>
            <div class="doctor-row__specialty">${doc.specialty}</div>
            <div class="doctor-row__meta">
                <span><i class="fas fa-briefcase"></i> ${doc.experience} yrs experience</span>
                <span><i class="fas fa-map-marker-alt"></i> ${doc.location}</span>
                ${modeLabel}
            </div>
            <span class="badge ${avail.cls} doctor-row__badge">${avail.text}</span>
        </div>
        <div class="doctor-row__actions">
            <a href="doctor-profile.html" class="btn btn-outline btn-sm">View Profile</a>
            <a href="register.html" class="btn btn-primary btn-sm">Book Appointment</a>
        </div>
    </div>`;
}

function swasthaiFilterDoctors() {
  const list = document.getElementById('doctorList');
  const countEl = document.getElementById('doctorCount');
  if (!list) return;

  const query = (document.getElementById('doctorSearchInput')?.value || '').trim().toLowerCase();
  const specialtyChecks = Array.from(document.querySelectorAll('.js-filter-specialty:checked')).map(el => el.value);
  const modeChecks = Array.from(document.querySelectorAll('.js-filter-mode:checked')).map(el => el.value);
  const availChecks = Array.from(document.querySelectorAll('.js-filter-availability:checked')).map(el => el.value);
  const minExperience = parseInt(document.querySelector('.js-filter-experience:checked')?.value || '0', 10);

  const results = SWASTHAI_DOCTORS.filter(doc => {
    const matchesQuery = !query || doc.name.toLowerCase().includes(query) || doc.specialty.toLowerCase().includes(query);
    const matchesSpecialty = specialtyChecks.length === 0 || specialtyChecks.includes(doc.specialtyKey);
    const matchesMode = modeChecks.length === 0 || doc.modes.some(m => modeChecks.includes(m));
    const matchesAvailability = availChecks.length === 0 || availChecks.includes(doc.availability);
    const matchesExperience = doc.experience >= minExperience;
    return matchesQuery && matchesSpecialty && matchesMode && matchesAvailability && matchesExperience;
  });

  list.innerHTML = results.length
    ? results.map(swasthaiDoctorRow).join('')
    : `<div class="doctor-empty"><i class="fas fa-user-md"></i><p>No doctors match your filters. Try broadening your search.</p></div>`;

  if (countEl) countEl.textContent = `${results.length} doctor${results.length === 1 ? '' : 's'} found`;
}

document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('doctorList')) return;

  swasthaiFilterDoctors();

  document.querySelectorAll('.js-doctor-filter').forEach(el => {
    el.addEventListener('change', swasthaiFilterDoctors);
  });

  const searchInput = document.getElementById('doctorSearchInput');
  if (searchInput) searchInput.addEventListener('input', swasthaiFilterDoctors);

  const searchBtn = document.getElementById('doctorSearchBtn');
  if (searchBtn) searchBtn.addEventListener('click', (e) => { e.preventDefault(); swasthaiFilterDoctors(); });

  const resetBtn = document.getElementById('doctorFilterReset');
  if (resetBtn) {
    resetBtn.addEventListener('click', (e) => {
      e.preventDefault();
      document.querySelectorAll('.js-doctor-filter').forEach(el => {
        if (el.type === 'checkbox') el.checked = false;
        if (el.type === 'radio') el.checked = el.value === '0';
      });
      if (searchInput) searchInput.value = '';
      swasthaiFilterDoctors();
    });
  }
});
