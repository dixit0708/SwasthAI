/**
 * SwasthAI — shared rendering helpers for the doctor directory pages
 * (doctors.html, doctor-profile.html). Every API value goes through
 * swasthaiEscapeHtml before it reaches innerHTML.
 */

const DOCTOR_KIND_LABELS = {
  hospital: 'Hospital',
  clinic: 'Clinic',
  doctor: 'Doctor',
  dentist: 'Dental clinic',
  centre: 'Health centre'
};

// Risk assessment key -> name shown when a result page links here.
const DOCTOR_ASSESSMENT_NAMES = {
  heart: 'Heart Risk Assessment',
  diabetes: 'Diabetes Risk Assessment',
  liver: 'Liver Risk Assessment',
  skin: 'Skin Analysis',
  pneumonia: 'Chest X-ray Analysis'
};

const DOCTOR_AVATAR_COLORS = ['#0F766E', '#0284C7', '#7C3AED', '#B45309', '#047857', '#BE123C', '#4338CA', '#0E7490'];

function doctorInitials(name) {
  const words = String(name || '')
    .replace(/^dr\.?\s+/i, '')
    .split(/\s+/)
    .filter((word) => /^[A-Za-z]/.test(word));
  return ((words[0] || '?')[0] + (words[1] ? words[1][0] : '')).toUpperCase();
}

function doctorAvatarHtml(name, large = false) {
  let hash = 0;
  for (const ch of String(name || '')) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  const color = DOCTOR_AVATAR_COLORS[hash % DOCTOR_AVATAR_COLORS.length];
  return `<div class="dir-avatar${large ? ' dir-avatar--lg' : ''}" style="background:${color}" aria-hidden="true">${swasthaiEscapeHtml(doctorInitials(name))}</div>`;
}

function doctorBadgesHtml(doc) {
  const esc = swasthaiEscapeHtml;
  const badges = [];
  if (doc.listed_with_consent) {
    badges.push('<span class="badge badge-success"><i class="fas fa-circle-check"></i> Listed with consent</span>');
  }
  if (doc.kind && DOCTOR_KIND_LABELS[doc.kind]) {
    badges.push(`<span class="badge badge-neutral">${esc(DOCTOR_KIND_LABELS[doc.kind])}</span>`);
  }
  const inferred = doc.specialty_source === 'name_match';
  (doc.specialties || []).forEach((spec) => {
    badges.push(
      `<span class="dir-spec-tag${inferred ? ' dir-spec-tag--inferred' : ''}"${inferred ? ' title="Matched from the listing name"' : ''}>${esc(spec.label)}</span>`
    );
  });
  return badges.join('');
}

function doctorActionsHtml(doc, { includeDetails = true } = {}) {
  const esc = swasthaiEscapeHtml;
  const actions = [];
  if (doc.phone_dial) {
    actions.push(`<a class="btn btn-primary btn-sm" href="tel:${esc(doc.phone_dial)}"><i class="fas fa-phone"></i> Call</a>`);
  }
  actions.push(
    `<a class="btn btn-outline btn-sm" href="${esc(doc.google_maps_url)}" target="_blank" rel="noopener noreferrer"><i class="fas fa-map-location-dot"></i> View on Google Maps<span class="sr-only"> (opens in a new tab)</span></a>`
  );
  actions.push(
    `<a class="btn btn-ghost btn-sm" href="${esc(doc.directions_url)}" target="_blank" rel="noopener noreferrer"><i class="fas fa-diamond-turn-right"></i> Directions<span class="sr-only"> (opens in a new tab)</span></a>`
  );
  if (includeDetails) {
    actions.push(`<a class="btn btn-ghost btn-sm" href="doctor-profile.html?id=${encodeURIComponent(doc.id)}">Details <i class="fas fa-arrow-right"></i></a>`);
  }
  return actions.join('');
}
