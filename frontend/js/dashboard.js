/**
 * SwasthAI — Dashboard hero shuffle grid.
 * Vanilla recreation of the "shuffle grid" effect (no React/framer-motion):
 * each tile is a persistent element holding one fixed image, and every few
 * seconds the tiles swap grid positions with a smooth animated slide — the
 * same visual result as framer-motion's `layout` animation, done here with
 * the FLIP technique (record First position, Let the reorder happen,
 * Invert with a transform, Play the transition back to identity).
 *
 */
const DASHBOARD_HERO_IMAGES = [
  'assets/images/dashboard-hero/hero-1.webp',
  'assets/images/dashboard-hero/hero-2.webp',
  'assets/images/dashboard-hero/hero-3.webp',
  'assets/images/dashboard-hero/hero-4.webp',
  'assets/images/dashboard-hero/hero-5.webp',
  'assets/images/dashboard-hero/hero-6.webp',
  'assets/images/dashboard-hero/hero-7.webp',
  'assets/images/dashboard-hero/hero-8.webp',
  'assets/images/dashboard-hero/hero-9.webp',
  'assets/images/dashboard-hero/hero-10.webp',
  'assets/images/dashboard-hero/hero-11.webp',
  'assets/images/dashboard-hero/hero-12.webp',
  'assets/images/dashboard-hero/hero-13.webp',
  'assets/images/dashboard-hero/hero-14.webp',
  'assets/images/dashboard-hero/hero-15.webp'
];

const DASHBOARD_HERO_GRID_CELLS = 15; // matches the 5x3 grid in css/dashboard.css — one tile per image, no repeats
const DASHBOARD_HERO_SHUFFLE_INTERVAL_MS = 3000;
const DASHBOARD_HERO_TRANSITION_MS = 700;

function shuffleArray(input) {
  const arr = input.slice();
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// Builds one persistent tile per grid cell, each permanently holding a
// single image (cycling through the provided list if there are fewer
// images than cells) — only each tile's grid position ever changes.
function buildTiles(grid) {
  const tiles = [];
  for (let i = 0; i < DASHBOARD_HERO_GRID_CELLS; i++) {
    const src = DASHBOARD_HERO_IMAGES[i % DASHBOARD_HERO_IMAGES.length];
    const tile = document.createElement('div');
    tile.className = 'dashboard-hero__tile';
    tile.style.backgroundImage = `url('${src}')`;
    tile.style.order = String(i);
    grid.appendChild(tile);
    tiles.push(tile);
  }
  return tiles;
}

function shuffleTilePositions(tiles, animate) {
  const orders = shuffleArray(tiles.map((_, i) => i));

  if (!animate) {
    tiles.forEach((tile, i) => { tile.style.order = String(orders[i]); });
    return;
  }

  // First: record each tile's current on-screen position.
  const firstRects = tiles.map((tile) => tile.getBoundingClientRect());

  // Let the reorder happen (CSS `order` changes where grid places each tile).
  tiles.forEach((tile, i) => { tile.style.order = String(orders[i]); });
  void tiles[0].offsetHeight; // force layout so new positions are committed

  // Invert: jump each tile back to where it visually was, with no transition.
  tiles.forEach((tile, i) => {
    const last = tile.getBoundingClientRect();
    const dx = firstRects[i].left - last.left;
    const dy = firstRects[i].top - last.top;
    tile.style.transition = 'none';
    tile.style.transform = `translate(${dx}px, ${dy}px)`;
  });
  void tiles[0].offsetHeight;

  // Play: animate back to the real (new) position.
  tiles.forEach((tile) => {
    tile.style.transition = `transform ${DASHBOARD_HERO_TRANSITION_MS}ms cubic-bezier(0.4, 0, 0.2, 1)`;
    tile.style.transform = 'translate(0, 0)';
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const grid = document.getElementById('dashboardHeroGrid');
  if (!grid) return;

  const tiles = buildTiles(grid);
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  setInterval(() => shuffleTilePositions(tiles, !reduceMotion), DASHBOARD_HERO_SHUFFLE_INTERVAL_MS);
});

/**
 * Dashboard data. Every tile and list below is filled from the signed-in
 * user's own records; when there is nothing yet, it says so and points to
 * the next step. Nothing here is sample data.
 */
function dashSet(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

function dashGreeting() {
  const user = typeof swasthaiCurrentUser === 'function' && swasthaiCurrentUser();
  const firstName = user && user.name ? user.name.trim().split(/\s+/)[0] : '';
  const hour = new Date().getHours();
  const partOfDay = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const greeting = document.getElementById('dashboardGreeting');
  if (greeting) greeting.textContent = firstName ? `${partOfDay}, ${firstName}` : partOfDay;
  const dateEl = document.getElementById('dashboardDate');
  if (dateEl) dateEl.textContent = AppUI.fmtDateLong(new Date());
}

function dashRenderAssessments(result) {
  if (result.status !== 'fulfilled') {
    dashSet('statAssessment', 'Unavailable');
    dashSet('statAssessmentHint', 'Could not load right now');
    dashSet('recentResults', AppUI.errorState(AppUI.errorText(result.reason)));
    return;
  }
  const { items, total } = result.value;
  if (!items.length) {
    dashSet('statAssessment', 'None yet');
    dashSet('statAssessmentHint', 'Takes about 3 minutes');
    dashSet('recentResults', AppUI.state({
      icon: 'fa-chart-line',
      title: 'No assessments yet',
      text: 'Answer a few questions to see your risk indicators for diabetes, heart or liver disease.',
      actionHtml: '<a class="btn btn-primary btn-compact" href="predictions.html">Start an assessment</a>'
    }));
    return;
  }
  const latest = items[0];
  dashSet('statAssessment', AppUI.esc(latest.condition_label.replace(/ \(.*\)$/, '')));
  dashSet('statAssessmentHint', `${AppUI.riskPill(latest)} <span style="margin-left:6px;">${AppUI.esc(AppUI.fmtDate(latest.created_at))}</span>`);
  dashSet('recentResults', `<ul class="rows">${items.map((item) => AppUI.predictionRow(item)).join('')}</ul>${
    total > items.length ? `<div class="pager"><span>Showing ${items.length} of ${total}</span><a class="panel__link" href="predictions.html#history">See all results</a></div>` : ''}`);
}

function dashRenderAppointments(result) {
  if (result.status !== 'fulfilled') {
    dashSet('statAppointment', 'Unavailable');
    dashSet('statAppointmentHint', 'Could not load right now');
    dashSet('upcomingAppointments', AppUI.errorState(AppUI.errorText(result.reason)));
    return;
  }
  const { items } = result.value;
  if (!items.length) {
    dashSet('statAppointment', 'Nothing scheduled');
    dashSet('statAppointmentHint', 'Find a doctor to plan a visit');
    dashSet('upcomingAppointments', AppUI.state({
      icon: 'fa-calendar-plus',
      title: 'No upcoming appointments',
      text: 'Find a doctor or clinic and add your visit here to keep track of it.',
      actionHtml: '<a class="btn btn-outline btn-compact" href="doctors.html">Find a doctor</a>'
    }));
    return;
  }
  const next = items[0];
  dashSet('statAppointment', `${AppUI.esc(AppUI.relativeDay(next.appointment_date))}, ${AppUI.esc(AppUI.fmtTime(next.appointment_time))}`);
  dashSet('statAppointmentHint', AppUI.esc(next.doctor_name));
  dashSet('upcomingAppointments', `<ul class="rows">${items.map((a) => `
    <li class="row-item">
      <span class="row-item__icon row-item__icon--blue"><i class="fas fa-calendar-day" aria-hidden="true"></i></span>
      <div class="row-item__main">
        <div class="row-item__title">${AppUI.esc(a.doctor_name)}</div>
        <div class="row-item__meta">${AppUI.esc(AppUI.fmtDate(a.appointment_date, { weekday: 'short', day: 'numeric', month: 'short' }))} at ${AppUI.esc(AppUI.fmtTime(a.appointment_time))}${a.patient_name ? ` &middot; for ${AppUI.esc(a.patient_name)}` : ''}</div>
      </div>
      <div class="row-item__aside">
        <span class="pill ${a.status === 'confirmed' ? 'pill--ok' : 'pill--warn'}">${a.status === 'confirmed' ? 'Confirmed' : 'Confirm with clinic'}</span>
      </div>
    </li>`).join('')}</ul>`);
}

function dashRenderFamily(result) {
  if (result.status !== 'fulfilled') {
    ['statMedications', 'statFamily'].forEach((id) => dashSet(id, '&ndash;'));
    dashSet('statMedicationsHint', 'Could not load right now');
    dashSet('statFamilyHint', 'Could not load right now');
    return;
  }
  const overview = result.value;
  const meds = (overview.active_medications || []).length || 0;
  dashSet('statMedications', String(overview.total_medications ?? meds));
  dashSet('statMedicationsHint', overview.total_medications ? 'Currently being taken' : 'Add medicines to keep a clear list');
  dashSet('statFamily', String(overview.total_members || 0));
  dashSet('statFamilyHint', overview.total_members
    ? `${overview.total_records || 0} health record${overview.total_records === 1 ? '' : 's'} stored`
    : 'Add yourself or a family member');
}

function dashRenderReports(result) {
  if (result.status !== 'fulfilled') {
    dashSet('recentReports', AppUI.errorState(AppUI.errorText(result.reason)));
    return;
  }
  const { items } = result.value;
  if (!items.length) {
    dashSet('recentReports', AppUI.state({
      icon: 'fa-file-medical',
      title: 'No reports analysed yet',
      text: 'Upload a lab report to see each value explained in plain language.',
      actionHtml: '<a class="btn btn-outline btn-compact" href="report-analyzer.html">Analyze a report</a>'
    }));
    return;
  }
  dashSet('recentReports', `<ul class="rows">${items.map((r) => `
    <li><a class="row-item" href="medical-records.html?report=${encodeURIComponent(r.id)}#reports" style="text-decoration:none;">
      <span class="row-item__icon row-item__icon--teal"><i class="fas fa-file-lines" aria-hidden="true"></i></span>
      <span class="row-item__main">
        <span class="row-item__title">${AppUI.esc(r.filename)}</span>
        <span class="row-item__meta" style="display:block;">${AppUI.esc(AppUI.fmtDate(r.created_at))} &middot; ${r.flagged_count ? `${r.flagged_count} value${r.flagged_count === 1 ? '' : 's'} to discuss` : 'All recognised values in range'}</span>
      </span>
    </a></li>`).join('')}</ul>`);
}

function dashRenderNudge(result) {
  const nudge = document.getElementById('dashboardNudge');
  if (!nudge || result.status !== 'fulfilled') return;
  const profile = result.value;
  const missing = [];
  if (!profile.date_of_birth) missing.push('date of birth');
  if (!profile.height_cm || !profile.weight_kg) missing.push('height and weight');
  if (!profile.occupation_type || !profile.diet_preference || !profile.cuisine_region) missing.push('daily routine and food habits');
  if (!missing.length) return;
  nudge.hidden = false;
  nudge.innerHTML = `
    <div class="notice" style="margin-bottom: var(--sp-6);">
      <i class="fas fa-user-pen" aria-hidden="true"></i>
      <span><strong>Get your personal Indian diet plan.</strong> Add your ${AppUI.esc(missing.join(', '))} so your meals and activity plan fit your day. <a href="diet-lifestyle.html">Answer a few questions</a></span>
    </div>`;
}

document.addEventListener('DOMContentLoaded', async () => {
  if (!document.getElementById('recentResults') || typeof SwasthAPI === 'undefined') return;
  dashGreeting();
  dashSet('recentResults', AppUI.skeletonRows(3));
  dashSet('upcomingAppointments', AppUI.skeletonRows(2));
  dashSet('recentReports', AppUI.skeletonRows(2));

  const [assessments, appointments, family, reports, profile] = await Promise.allSettled([
    SwasthAPI.predictions.history({ page_size: 5 }),
    SwasthAPI.appointments.list('upcoming', 1, 3),
    SwasthAPI.family.getOverview(),
    SwasthAPI.reportAnalysis.history(1, 3),
    SwasthAPI.healthProfile.get()
  ]);

  dashRenderAssessments(assessments);
  dashRenderAppointments(appointments);
  dashRenderFamily(family);
  dashRenderReports(reports);
  dashRenderNudge(profile);
});
