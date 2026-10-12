/**
 * SwasthAI — Doctor details (doctor-profile.html?id=<doctor id>).
 * Loads one listing via GET /api/v1/doctors/{id}. The map is an
 * OpenStreetMap embed: free, no API key, and no data leaves SwasthAI
 * beyond the listing's own coordinates.
 */

function dpFact(icon, label, valueHtml) {
  return `
    <li>
      <span class="profile-facts__icon" aria-hidden="true"><i class="fas ${icon}"></i></span>
      <span><span class="profile-facts__label">${label}</span><span class="profile-facts__value">${valueHtml}</span></span>
    </li>`;
}

function dpMapHtml(doc) {
  if (typeof doc.latitude !== 'number' || typeof doc.longitude !== 'number') {
    return `<p class="text-muted" style="margin:0;">Map location isn't available for this listing. Use Google Maps to find it.</p>`;
  }
  const lat = doc.latitude;
  const lng = doc.longitude;
  const bbox = [lng - 0.006, lat - 0.004, lng + 0.006, lat + 0.004].map((n) => n.toFixed(6)).join(',');
  const embed = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat.toFixed(6)},${lng.toFixed(6)}`;
  const full = `https://www.openstreetmap.org/?mlat=${lat.toFixed(6)}&mlon=${lng.toFixed(6)}#map=17/${lat.toFixed(6)}/${lng.toFixed(6)}`;
  return `
    <iframe class="profile-map" src="${embed}" title="Map showing ${swasthaiEscapeHtml(doc.name)}" loading="lazy" referrerpolicy="no-referrer"></iframe>
    <a class="profile-map__link" href="${full}" target="_blank" rel="noopener noreferrer">View larger map <i class="fas fa-arrow-up-right-from-square"></i><span class="sr-only"> (opens in a new tab)</span></a>`;
}

function dpRender(doc) {
  const esc = swasthaiEscapeHtml;
  const kind = DOCTOR_KIND_LABELS[doc.kind] || 'Healthcare provider';
  const subtitle = [doc.qualification, doc.clinic_name, doc.city].filter(Boolean).map(esc).join(' · ') || esc(kind);

  const facts = [];
  if (doc.address) facts.push(dpFact('fa-location-dot', 'Address', esc(doc.address)));
  if (doc.phone) facts.push(dpFact('fa-phone', 'Phone', `<a href="tel:${esc(doc.phone_dial)}">${esc(doc.phone)}</a>`));
  if (doc.timings) facts.push(dpFact('fa-clock', 'Consultation timings', esc(doc.timings)));

  const contactNote = doc.listed_with_consent
    ? `<div class="profile-note"><i class="fas fa-circle-check"></i><span>${esc(doc.attribution)} Please call ahead to confirm timings before visiting.</span></div>`
    : `<div class="profile-note"><i class="fas fa-circle-info"></i><span>This is a public listing, so SwasthAI doesn't hold its phone number. Open it on Google Maps to see current contact details and opening hours. ${esc(doc.attribution)}</span></div>`;

  const specialtyNote = doc.specialty_source === 'name_match'
    ? '<p class="text-muted" style="font-size: var(--text-xs); margin: var(--sp-2) 0 0;">Specialty matched from the listing name.</p>'
    : '';

  document.title = `SwasthAI - ${doc.name}`;
  document.getElementById('dpContent').innerHTML = `
    <section class="profile-hero">
      ${doctorAvatarHtml(doc.name, true)}
      <div>
        <h1 class="profile-hero__name">${esc(doc.name)}</h1>
        <p class="profile-hero__meta">${subtitle}</p>
        <div class="dir-card__badges">${doctorBadgesHtml(doc)}</div>
        ${specialtyNote}
      </div>
    </section>

    <div class="profile-grid">
      <div>
        <section class="profile-card">
          <h2 class="profile-card__title">Contact &amp; location</h2>
          ${facts.length ? `<ul class="profile-facts">${facts.join('')}</ul>` : ''}
          <div class="profile-actions">${doctorActionsHtml(doc, { includeDetails: false }).replace(/btn-sm/g, '')}</div>
          ${contactNote}
        </section>

        <section class="profile-card">
          <h2 class="profile-card__title">Before your visit</h2>
          <ul class="profile-tips">
            <li><i class="fas fa-check"></i><span>Carry your previous prescriptions and recent test reports.</span></li>
            <li><i class="fas fa-check"></i><span>Have a lab report you don't understand? Get a plain-language summary with the <a href="report-analyzer.html">Report Analyzer</a> first.</span></li>
            <li><i class="fas fa-check"></i><span>Share any SwasthAI risk assessment with the doctor. It's an AI insight to discuss, not a diagnosis.</span></li>
          </ul>
        </section>
      </div>

      <section class="profile-card">
        <h2 class="profile-card__title">On the map</h2>
        ${dpMapHtml(doc)}
      </section>
    </div>`;
}

function dpRenderState({ error, title, text }) {
  document.getElementById('dpContent').innerHTML = `
    <div class="dir-state${error ? ' dir-state--error' : ''}">
      <div class="dir-state__icon"><i class="fas ${error ? 'fa-triangle-exclamation' : 'fa-hospital-user'}"></i></div>
      <p class="dir-state__title">${swasthaiEscapeHtml(title)}</p>
      <p class="dir-state__text">${swasthaiEscapeHtml(text)}</p>
      <div style="display:flex; gap: var(--sp-3); justify-content:center; flex-wrap:wrap;">
        ${error ? '<button type="button" class="btn btn-primary" id="dpRetry">Try again</button>' : ''}
        <a href="doctors.html" class="btn btn-outline">Browse all doctors</a>
      </div>
    </div>`;
  const retry = document.getElementById('dpRetry');
  if (retry) retry.addEventListener('click', dpLoad);
}

async function dpLoad() {
  const id = new URLSearchParams(window.location.search).get('id');
  if (!id) {
    dpRenderState({ title: 'No doctor selected', text: 'Choose a listing from the directory to see its details.' });
    return;
  }
  try {
    dpRender(await SwasthAPI.doctors.get(id));
  } catch (err) {
    if (err.status === 404) {
      dpRenderState({ title: 'This listing is no longer available', text: 'It may have closed or been removed from the directory.' });
    } else {
      dpRenderState({ error: true, title: 'We couldn’t load this listing', text: err.status ? err.message : 'Please check your internet connection and try again.' });
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('dpContent')) return;

  // Return to the exact filtered list the user came from, if they came from it.
  const back = document.getElementById('dpBack');
  if (document.referrer) {
    try {
      const ref = new URL(document.referrer);
      if (ref.origin === window.location.origin && /\/doctors(\.html)?$/.test(ref.pathname)) {
        back.href = `doctors.html${ref.search}`;
      }
    } catch (err) { /* malformed referrer: keep the default link */ }
  }

  dpLoad();
});
