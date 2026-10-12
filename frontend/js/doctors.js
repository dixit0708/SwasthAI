/**
 * SwasthAI — Doctor directory (doctors.html).
 * Lists real hospitals/clinics (OpenStreetMap) and doctors who agreed to be
 * listed, via GET /api/v1/doctors/search, nearest first, with a Leaflet map.
 *
 * Location: the browser's position is used only after the user allows it,
 * and only sent as lat/lng on the search request. It is never stored, and
 * never put in the URL (only a `near=me` flag is). Without it, distances are
 * measured from Moradabad city centre.
 *
 * URL params: q, specialty, consented=1, from=<assessment key>, near=me
 */

const DIR_PAGE_SIZE = 20;
const DIR_QUICK_SPECIALTIES = ['general', 'cardiology', 'endocrinology', 'gynecology', 'pediatrics', 'orthopedics', 'ophthalmology', 'dental'];
const DIR_DEFAULT_ORIGIN = { lat: 28.8386, lng: 78.7733, label: 'Moradabad city centre', precise: false };

const dirState = {
  q: '',
  specialty: '',
  consentedOnly: false,
  from: '',
  origin: DIR_DEFAULT_ORIGIN,
  view: 'google',
  area: '',
  page: 1,
  loaded: 0,
  total: 0,
  requestSeq: 0,
  groupShown: false,
  specialties: []
};

const dirEl = {};
const dirMap = { map: null, layer: null, originMarker: null, markers: new Map() };

function dirShortLabel(label) {
  return label.replace(/\s*\(.*\)$/, '');
}

function dirSpecialtyLabel(key) {
  const spec = dirState.specialties.find((s) => s.key === key);
  return spec ? spec.label : '';
}

function dirFormatDistance(km) {
  if (typeof km !== 'number') return '';
  return km < 10 ? `${km.toFixed(1)} km` : `${Math.round(km)} km`;
}

function dirSyncUrl() {
  const params = new URLSearchParams();
  if (dirState.q) params.set('q', dirState.q);
  if (dirState.specialty) params.set('specialty', dirState.specialty);
  if (dirState.consentedOnly) params.set('consented', '1');
  if (dirState.from) params.set('from', dirState.from);
  if (dirState.origin.precise) params.set('near', 'me');
  if (dirState.view === 'directory') params.set('view', 'directory');
  if (dirState.area) params.set('area', dirState.area);
  const query = params.toString();
  history.replaceState(null, '', query ? `?${query}` : window.location.pathname);
}

/* ── Google Maps results tab ─────────────────────────────────────────────── */
// Google renders its own results in its own embed: nothing is fetched,
// copied or stored by SwasthAI, and no key or billing is involved. The
// iframe is only given a URL while its tab is open, so Google receives
// nothing (including the user's location) unless the user opens it.

// Real localities, chosen by how often they appear in the addresses of the
// imported Moradabad listings, plus the district's towns. Each area x
// specialty pair is a separate Google search with its own result set, which
// is how users can reach well beyond Google's per-search limit.
const DIR_GOOGLE_AREAS = {
  'Moradabad city': [
    'Civil Lines', 'Gandhi Nagar', 'Lajpat Nagar', 'Kanth Road', 'Ashiyana Colony', 'Harthala',
    'Pili Kothi', 'Katghar', 'Delhi Road', 'Rampur Road', 'Station Road', 'Ram Ganga Vihar',
    'Buddhi Vihar', 'Avas Vikas', 'Deputy Ganj', 'Majhola'
  ],
  'Towns in the district': ['Thakurdwara', 'Bilari', 'Kanth', 'Kundarki']
};
const DIR_GOOGLE_AREA_LIST = ['', ...Object.values(DIR_GOOGLE_AREAS).flat()];

function dirRenderGoogleAreas() {
  const esc = swasthaiEscapeHtml;
  const groups = Object.entries(DIR_GOOGLE_AREAS).map(([group, areas]) =>
    `<optgroup label="${esc(group)}">${areas.map((a) => `<option value="${esc(a)}">${esc(a)}</option>`).join('')}</optgroup>`);
  dirEl.googleArea.innerHTML = `<option value="">Nearest to ${dirState.origin.precise ? 'me' : 'city centre'}</option>${groups.join('')}`;
  dirEl.googleArea.value = dirState.area;
}

function dirSetArea(area) {
  dirState.area = DIR_GOOGLE_AREA_LIST.includes(area) ? area : '';
  dirEl.googleArea.value = dirState.area;
  const index = DIR_GOOGLE_AREA_LIST.indexOf(dirState.area);
  const count = DIR_GOOGLE_AREA_LIST.length - 1;
  dirEl.googleStep.textContent = index > 0 ? `Area ${index} of ${count}` : `${count} areas to explore`;
  dirSyncUrl();
  dirUpdateGoogle();
}

function dirStepArea(delta) {
  const list = DIR_GOOGLE_AREA_LIST;
  const index = list.indexOf(dirState.area);
  dirSetArea(list[(index + delta + list.length) % list.length]);
}

function dirGoogleTerm() {
  const label = dirSpecialtyLabel(dirState.specialty);
  const term = label ? dirShortLabel(label).split(/\s*[/&]\s*/)[0].trim() : 'doctor';
  return [dirState.q, term].filter(Boolean).join(' ');
}

function dirGoogleQuery() {
  const { origin, area } = dirState;
  if (area) return `${dirGoogleTerm()} in ${area}, Moradabad`;
  const where = origin.precise ? `${origin.lat.toFixed(4)},${origin.lng.toFixed(4)}` : 'Moradabad';
  return `${dirGoogleTerm()} near ${where}`;
}

function dirGoogleQueryLabel() {
  if (dirState.area) return `${dirGoogleTerm()} in ${dirState.area}`;
  return `${dirGoogleTerm()} near ${dirState.origin.precise ? 'your location' : 'Moradabad'}`;
}

function dirUpdateGoogle() {
  if (dirState.view !== 'google') return;
  const query = dirGoogleQuery();
  const src = `https://www.google.com/maps?${new URLSearchParams({ q: query, output: 'embed' })}`;
  if (dirEl.googleFrame.getAttribute('src') !== src) dirEl.googleFrame.setAttribute('src', src);
  dirEl.googleOpen.href = `https://www.google.com/maps/search/?${new URLSearchParams({ api: '1', query })}`;
  dirEl.googleQuery.textContent = dirGoogleQueryLabel();
  dirEl.googleOpenLabel.textContent = `See all ${dirGoogleTerm()} results on Google Maps`;
}

function dirSetView(view, { focus = false } = {}) {
  dirState.view = view === 'directory' ? 'directory' : 'google';
  const google = dirState.view === 'google';
  dirEl.tabDirectory.setAttribute('aria-selected', String(!google));
  dirEl.tabGoogle.setAttribute('aria-selected', String(google));
  dirEl.tabDirectory.tabIndex = google ? -1 : 0;
  dirEl.tabGoogle.tabIndex = google ? 0 : -1;
  dirEl.layout.hidden = google;
  dirEl.googlePanel.hidden = !google;
  dirEl.locationBar.classList.toggle('is-google', google);
  if (focus) (google ? dirEl.tabGoogle : dirEl.tabDirectory).focus();
  if (google) dirUpdateGoogle();
  else if (dirMap.map) {
    // The map was sized while hidden; re-measure, then re-fit its pins.
    dirMap.map.invalidateSize();
    dirFitMap();
  }
  dirRenderLocation();
  dirSyncUrl();
}

/* ── Location ────────────────────────────────────────────────────────────── */

function dirRenderLocation(message) {
  const precise = dirState.origin.precise;
  dirEl.locationBar.classList.toggle('is-precise', precise);
  const where = precise ? 'your location' : swasthaiEscapeHtml(dirState.origin.label);
  dirEl.locationText.innerHTML = message
    ? swasthaiEscapeHtml(message)
    : dirState.view === 'google'
      ? `Showing Google Maps results near <strong>${precise ? 'your location' : 'Moradabad'}</strong>`
      : `Sorted by distance from <strong>${where}</strong>`;
  dirEl.useLocation.innerHTML = precise
    ? '<i class="fas fa-location-crosshairs"></i> Update my location'
    : '<i class="fas fa-location-arrow"></i> Use my location';
  if (dirEl.googleArea) dirRenderGoogleAreas();
}

function dirRequestLocation() {
  if (!('geolocation' in navigator)) {
    dirRenderLocation('Your browser can’t share location. Showing distances from Moradabad city centre.');
    return;
  }
  dirEl.useLocation.disabled = true;
  dirEl.useLocation.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Locating…';
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      dirEl.useLocation.disabled = false;
      dirState.origin = { lat: pos.coords.latitude, lng: pos.coords.longitude, label: 'your location', precise: true };
      dirRenderLocation();
      dirSyncUrl();
      dirUpdateGoogle();
      dirLoad();
    },
    (err) => {
      dirEl.useLocation.disabled = false;
      dirState.origin = DIR_DEFAULT_ORIGIN;
      dirSyncUrl();
      dirRenderLocation(err.code === err.PERMISSION_DENIED
        ? 'Location access was blocked. Showing distances from Moradabad city centre. You can allow it in your browser’s site settings.'
        : 'Couldn’t get your location right now. Showing distances from Moradabad city centre.');
    },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
  );
}

// Use location automatically only if the user already granted it before.
async function dirLocationAlreadyAllowed() {
  try {
    const status = await navigator.permissions.query({ name: 'geolocation' });
    return status.state === 'granted';
  } catch (err) {
    return false;
  }
}

/* ── Map ─────────────────────────────────────────────────────────────────── */

function dirInitMap() {
  if (typeof L === 'undefined') {
    dirEl.mapPanel.classList.add('is-unavailable'); // CDN blocked: the list still works
    dirEl.mapToggle.hidden = true;
    return;
  }
  dirMap.map = L.map('dirMap', { scrollWheelZoom: false, zoomControl: true })
    .setView([dirState.origin.lat, dirState.origin.lng], 13);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors'
  }).addTo(dirMap.map);
  dirMap.layer = L.layerGroup().addTo(dirMap.map);
}

function dirMarkerStyle(doc, highlighted) {
  return {
    radius: highlighted ? 11 : 7,
    color: '#FFFFFF',
    weight: 2,
    fillColor: doc.listed_with_consent ? '#059669' : '#0F766E',
    fillOpacity: 1
  };
}

function dirPopupHtml(doc) {
  const esc = swasthaiEscapeHtml;
  const meta = [DOCTOR_KIND_LABELS[doc.kind], dirFormatDistance(doc.distance_km)].filter(Boolean).map(esc).join(' · ');
  return `
    <div class="dir-popup">
      <p class="dir-popup__name">${esc(doc.name)}</p>
      ${meta ? `<p class="dir-popup__meta">${meta}</p>` : ''}
      <a href="doctor-profile.html?id=${encodeURIComponent(doc.id)}">View details →</a>
    </div>`;
}

function dirUpdateMap(items, { append }) {
  if (!dirMap.map) return;
  if (!append) {
    dirMap.layer.clearLayers();
    dirMap.markers.clear();
  }

  if (dirMap.originMarker) dirMap.originMarker.remove();
  dirMap.originMarker = L.circleMarker([dirState.origin.lat, dirState.origin.lng], {
    radius: 8, color: '#FFFFFF', weight: 3, fillColor: dirState.origin.precise ? '#0284C7' : '#64748B', fillOpacity: 1
  }).bindTooltip(dirState.origin.precise ? 'You are here' : 'Moradabad city centre').addTo(dirMap.map);

  items.forEach((doc) => {
    if (typeof doc.latitude !== 'number' || typeof doc.longitude !== 'number') return;
    const marker = L.circleMarker([doc.latitude, doc.longitude], dirMarkerStyle(doc, false))
      .bindPopup(dirPopupHtml(doc))
      .addTo(dirMap.layer);
    marker.on('click', () => dirHighlightCard(doc.id));
    dirMap.markers.set(doc.id, { marker, doc });
  });

  if (!append) dirFitMap();
}

function dirFitMap() {
  if (!dirMap.map) return;
  const points = [[dirState.origin.lat, dirState.origin.lng]];
  dirMap.markers.forEach(({ doc }) => points.push([doc.latitude, doc.longitude]));
  if (points.length > 1) dirMap.map.fitBounds(points, { padding: [32, 32], maxZoom: 15 });
  else dirMap.map.setView(points[0], 13);
}

function dirHighlightMarker(id, on) {
  const entry = dirMap.markers.get(id);
  if (!entry) return;
  entry.marker.setStyle(dirMarkerStyle(entry.doc, on));
  if (on) entry.marker.bringToFront();
}

function dirHighlightCard(id) {
  const card = dirEl.list.querySelector(`.dir-card[data-id="${CSS.escape(id)}"]`);
  if (!card) return;
  dirEl.list.querySelectorAll('.dir-card.is-highlighted').forEach((el) => el.classList.remove('is-highlighted'));
  card.classList.add('is-highlighted');
  card.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'nearest' });
}

/* ── Rendering ───────────────────────────────────────────────────────────── */

function dirRenderChips() {
  const esc = swasthaiEscapeHtml;
  const chips = [`<button type="button" class="dir-chip" data-specialty="" aria-pressed="${!dirState.specialty}">All</button>`];
  DIR_QUICK_SPECIALTIES.forEach((key) => {
    const label = dirSpecialtyLabel(key);
    if (!label) return;
    chips.push(`<button type="button" class="dir-chip" data-specialty="${esc(key)}" aria-pressed="${dirState.specialty === key}">${esc(dirShortLabel(label))}</button>`);
  });
  // A specialty reached via the dropdown or a result link that isn't a quick chip still gets one.
  if (dirState.specialty && !DIR_QUICK_SPECIALTIES.includes(dirState.specialty)) {
    chips.push(`<button type="button" class="dir-chip" data-specialty="${esc(dirState.specialty)}" aria-pressed="true">${esc(dirShortLabel(dirSpecialtyLabel(dirState.specialty)))}</button>`);
  }
  chips.push(`<button type="button" class="dir-chip dir-chip--consent" data-consent aria-pressed="${dirState.consentedOnly}"><i class="fas fa-circle-check"></i> Listed with consent</button>`);
  dirEl.chips.innerHTML = chips.join('');
}

function dirRenderContext() {
  const assessment = DOCTOR_ASSESSMENT_NAMES[dirState.from];
  const specialtyLabel = dirSpecialtyLabel(dirState.specialty);
  if (!assessment || !specialtyLabel) {
    dirEl.context.hidden = true;
    return;
  }
  dirEl.contextTitle.textContent = `Following up on your ${assessment}`;
  dirEl.contextText.textContent =
    `A ${dirShortLabel(specialtyLabel).toLowerCase()} is the right specialist to discuss your result with. ` +
    'AI insights are not a diagnosis — a qualified doctor can confirm what it means for you.';
  dirEl.context.hidden = false;
}

function dirCardHtml(doc, index) {
  const esc = swasthaiEscapeHtml;
  const address = doc.address
    ? `<p class="dir-card__address"><i class="fas fa-location-dot" aria-hidden="true"></i><span>${esc(doc.address)}</span></p>`
    : '';
  const distance = typeof doc.distance_km === 'number'
    ? `<span class="dir-distance" title="Straight-line distance"><i class="fas fa-route" aria-hidden="true"></i> ${esc(dirFormatDistance(doc.distance_km))}</span>`
    : '';
  return `
    <article class="dir-card" data-id="${esc(doc.id)}" style="animation-delay:${Math.min(index, 10) * 30}ms">
      ${doctorAvatarHtml(doc.name)}
      <div>
        <div class="dir-card__top">
          <a class="dir-card__name" href="doctor-profile.html?id=${encodeURIComponent(doc.id)}">${esc(doc.name)}</a>
          ${distance}
        </div>
        <div class="dir-card__badges">${doctorBadgesHtml(doc)}</div>
        ${address}
      </div>
      <div class="dir-card__actions">${doctorActionsHtml(doc)}</div>
    </article>`;
}

function dirShowSkeleton() {
  dirEl.list.innerHTML = '<div class="dir-skeleton"></div>'.repeat(4);
  dirEl.list.setAttribute('aria-busy', 'true');
  dirEl.more.hidden = true;
  dirEl.count.textContent = 'Loading listings…';
}

function dirShowState({ error = false, title, text, actionLabel, onAction }) {
  dirEl.list.innerHTML = `
    <div class="dir-state${error ? ' dir-state--error' : ''}">
      <div class="dir-state__icon"><i class="fas ${error ? 'fa-triangle-exclamation' : 'fa-hospital-user'}"></i></div>
      <p class="dir-state__title">${swasthaiEscapeHtml(title)}</p>
      <p class="dir-state__text">${swasthaiEscapeHtml(text)}</p>
      ${actionLabel ? `<button type="button" class="btn btn-outline" id="dirStateAction">${swasthaiEscapeHtml(actionLabel)}</button>` : ''}
    </div>`;
  dirEl.list.setAttribute('aria-busy', 'false');
  dirEl.more.hidden = true;
  const actionBtn = document.getElementById('dirStateAction');
  if (actionBtn && onAction) actionBtn.addEventListener('click', onAction);
}

function dirUpdateCount(data) {
  const label = dirSpecialtyLabel(dirState.specialty);
  if (label && typeof data.specialty_matches === 'number') {
    const general = data.total - data.specialty_matches;
    const parts = [`${data.specialty_matches} ${dirShortLabel(label)} ${data.specialty_matches === 1 ? 'listing' : 'listings'}`];
    if (general > 0) parts.push(`${general} general & multi-specialty hospitals`);
    dirEl.count.textContent = parts.join(' + ');
    return;
  }
  dirEl.count.textContent = `${data.total} ${data.total === 1 ? 'listing' : 'listings'}`;
}

// Shown once, before the first general-care listing in a specialty search.
function dirGroupHtml(matchCount) {
  const label = dirShortLabel(dirSpecialtyLabel(dirState.specialty)).toLowerCase();
  const title = 'General & multi-specialty hospitals';
  const text = matchCount
    ? `These hospitals provide broad care and may also have a ${swasthaiEscapeHtml(label)}. Call ahead or check Google Maps to confirm.`
    : `No listing here has “${swasthaiEscapeHtml(label)}” in its name yet. These hospitals provide broad care and may offer it. Call ahead or check Google Maps to confirm.`;
  return `
    <div class="dir-group" role="note">
      <i class="fas fa-hospital" aria-hidden="true"></i>
      <div><p class="dir-group__title">${title}</p><p class="dir-group__text">${text}</p></div>
    </div>`;
}

/* ── Data ────────────────────────────────────────────────────────────────── */

async function dirLoad({ append = false } = {}) {
  const seq = ++dirState.requestSeq;
  dirState.page = append ? dirState.page + 1 : 1;
  if (!append) {
    dirShowSkeleton();
    dirState.groupShown = false;
  }
  dirEl.moreBtn.disabled = true;

  try {
    const data = await SwasthAPI.doctors.search({
      q: dirState.q,
      specialty: dirState.specialty,
      consented_only: dirState.consentedOnly ? 'true' : '',
      lat: dirState.origin.lat.toFixed(5),
      lng: dirState.origin.lng.toFixed(5),
      page: dirState.page,
      page_size: DIR_PAGE_SIZE
    });
    if (seq !== dirState.requestSeq) return; // a newer search superseded this one

    dirState.total = data.total;
    dirState.loaded = append ? dirState.loaded + data.items.length : data.items.length;
    dirUpdateCount(data);

    if (!append && data.items.length === 0) {
      dirUpdateMap([], { append: false });
      const filtered = dirState.q || dirState.specialty || dirState.consentedOnly;
      dirShowState(filtered
        ? { title: 'No listings match your search', text: 'Try a different name or area, or clear the filters to see every hospital and clinic.', actionLabel: 'Clear filters', onAction: dirClearFilters }
        : { title: 'No listings available yet', text: 'The directory for this city is being prepared. Please check back soon.' });
      return;
    }

    const html = data.items.map((doc, i) => {
      let group = '';
      if (doc.relevance === 'general_care' && !dirState.groupShown) {
        dirState.groupShown = true;
        group = dirGroupHtml(data.specialty_matches);
      }
      return group + dirCardHtml(doc, i);
    }).join('');
    if (append) dirEl.list.insertAdjacentHTML('beforeend', html);
    else dirEl.list.innerHTML = html;
    dirEl.list.setAttribute('aria-busy', 'false');
    dirEl.more.hidden = dirState.loaded >= dirState.total;
    dirUpdateMap(data.items, { append });
  } catch (err) {
    if (seq !== dirState.requestSeq) return;
    if (append) dirState.page -= 1;
    dirEl.count.textContent = 'Could not load listings';
    dirShowState({
      error: true,
      title: 'We couldn’t load the directory',
      text: err.status ? err.message : 'Please check your internet connection and try again.',
      actionLabel: 'Try again',
      onAction: () => dirLoad()
    });
  } finally {
    dirEl.moreBtn.disabled = false;
  }
}

function dirApplyFilters() {
  dirState.q = dirEl.query.value.trim();
  dirState.specialty = dirEl.specialty.value;
  if (!dirState.specialty) dirState.from = '';
  dirSyncUrl();
  dirRenderChips();
  dirRenderContext();
  dirUpdateGoogle();
  dirLoad();
}

function dirClearFilters() {
  dirEl.query.value = '';
  dirEl.specialty.value = '';
  dirState.consentedOnly = false;
  dirApplyFilters();
}

async function dirLoadSpecialties() {
  try {
    dirState.specialties = await SwasthAPI.doctors.specialties();
  } catch (err) {
    dirState.specialties = []; // search still works without the dropdown
  }
  const esc = swasthaiEscapeHtml;
  dirEl.specialty.insertAdjacentHTML('beforeend', dirState.specialties
    .map((s) => `<option value="${esc(s.key)}">${esc(s.label)}</option>`).join(''));
  if (!dirState.specialties.some((s) => s.key === dirState.specialty)) dirState.specialty = '';
  dirEl.specialty.value = dirState.specialty;
}

/* ── Init ────────────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', async () => {
  ['list', 'count', 'more', 'moreBtn', 'chips', 'context', 'contextTitle', 'contextText', 'query', 'specialty',
    'locationBar', 'locationText', 'useLocation', 'mapToggle', 'mapPanel', 'layout',
    'tabDirectory', 'tabGoogle', 'googlePanel', 'googleFrame', 'googleOpen', 'googleQuery',
    'googleArea', 'googlePrev', 'googleNext', 'googleStep', 'googleOpenLabel']
    .forEach((key) => { dirEl[key] = document.getElementById(`dir${key[0].toUpperCase()}${key.slice(1)}`); });
  if (!dirEl.list) return;

  const params = new URLSearchParams(window.location.search);
  dirState.q = (params.get('q') || '').slice(0, 80);
  dirState.specialty = params.get('specialty') || '';
  dirState.consentedOnly = params.get('consented') === '1';
  dirState.from = params.get('from') || '';
  dirEl.query.value = dirState.q;

  dirShowSkeleton();
  dirInitMap();
  dirRenderLocation();
  await dirLoadSpecialties();
  dirRenderChips();
  dirRenderContext();
  dirState.area = DIR_GOOGLE_AREA_LIST.includes(params.get('area')) ? params.get('area') : '';
  dirRenderGoogleAreas();
  dirSetArea(dirState.area);
  dirSetView(params.get('view'));
  dirLoad();

  dirEl.googleArea.addEventListener('change', () => dirSetArea(dirEl.googleArea.value));
  dirEl.googlePrev.addEventListener('click', () => dirStepArea(-1));
  dirEl.googleNext.addEventListener('click', () => dirStepArea(1));

  [dirEl.tabDirectory, dirEl.tabGoogle].forEach((tab) => {
    tab.addEventListener('click', () => dirSetView(tab === dirEl.tabGoogle ? 'google' : 'directory'));
    tab.addEventListener('keydown', (e) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
      e.preventDefault();
      const next = e.key === 'Home' ? 'google' : e.key === 'End' ? 'directory'
        : (dirState.view === 'google' ? 'directory' : 'google');
      dirSetView(next, { focus: true });
    });
  });

  // Re-use location without a prompt if the user allowed it before.
  if (params.get('near') === 'me' || await dirLocationAlreadyAllowed()) dirRequestLocation();

  document.getElementById('dirSearchForm').addEventListener('submit', (e) => {
    e.preventDefault();
    dirApplyFilters();
  });

  let debounce;
  dirEl.query.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(dirApplyFilters, 350);
  });
  dirEl.specialty.addEventListener('change', dirApplyFilters);

  dirEl.chips.addEventListener('click', (e) => {
    const chip = e.target.closest('.dir-chip');
    if (!chip) return;
    if (chip.hasAttribute('data-consent')) {
      dirState.consentedOnly = !dirState.consentedOnly;
    } else {
      dirEl.specialty.value = chip.dataset.specialty;
    }
    dirApplyFilters();
  });

  dirEl.moreBtn.addEventListener('click', () => dirLoad({ append: true }));
  dirEl.useLocation.addEventListener('click', dirRequestLocation);

  // Card hover/focus highlights its pin on the map.
  ['mouseover', 'focusin'].forEach((evt) => dirEl.list.addEventListener(evt, (e) => {
    const card = e.target.closest('.dir-card');
    if (card) dirHighlightMarker(card.dataset.id, true);
  }));
  ['mouseout', 'focusout'].forEach((evt) => dirEl.list.addEventListener(evt, (e) => {
    const card = e.target.closest('.dir-card');
    if (card && !card.contains(e.relatedTarget)) dirHighlightMarker(card.dataset.id, false);
  }));

  dirEl.mapToggle.addEventListener('click', () => {
    const hidden = dirEl.layout.classList.toggle('is-map-hidden');
    dirEl.mapToggle.setAttribute('aria-expanded', String(!hidden));
    dirEl.mapToggle.innerHTML = hidden ? '<i class="fas fa-map"></i> Show map' : '<i class="fas fa-map"></i> Hide map';
    if (!hidden && dirMap.map) dirMap.map.invalidateSize();
  });

  document.getElementById('dirContextClose').addEventListener('click', () => {
    dirState.from = '';
    dirSyncUrl();
    dirEl.context.hidden = true;
  });
});
