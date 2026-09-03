/**
 * SwasthAI — Authenticated app header, mobile nav drawer,
 * notifications panel and profile menu.
 * Injects into #header-container (top app header) and reuses
 * #sidebar-container as an off-canvas mobile nav drawer.
 */

const SWASTHAI_APP_NAV_LINKS = [
  { key: 'dashboard', label: 'Dashboard', href: 'dashboard.html' },
  { key: 'my-health', label: 'My Health', href: 'health-profile.html' },
  { key: 'ai-insights', label: 'AI Insights', href: 'predictions.html' },
  { key: 'family', label: 'Family', href: 'family.html' },
  { key: 'doctors', label: 'Doctors', href: 'doctors.html' }
];

// Maps every real app page to the primary nav section it belongs under,
// so deep pages (e.g. a single prediction form) still highlight the right tab.
const SWASTHAI_APP_PAGE_SECTIONS = {
  'dashboard.html': 'dashboard',
  'health-profile.html': 'my-health',
  'medical-records.html': 'my-health',
  'medications.html': 'my-health',
  'diet-lifestyle.html': 'my-health',
  'health-tracking.html': 'my-health',
  'predictions.html': 'ai-insights',
  'prediction-diabetes.html': 'ai-insights',
  'prediction-heart.html': 'ai-insights',
  'prediction-liver.html': 'ai-insights',
  'prediction-pneumonia.html': 'ai-insights',
  'prediction-skin.html': 'ai-insights',
  'report-analyzer.html': 'ai-insights',
  'ai-assistant.html': 'ai-insights',
  'family.html': 'family',
  'doctors.html': 'doctors',
  'doctor-profile.html': 'doctors',
  'appointments.html': 'doctors'
};

function swasthaiCurrentAppSection() {
  const file = window.location.pathname.split('/').pop() || 'dashboard.html';
  return SWASTHAI_APP_PAGE_SECTIONS[file] || '';
}

function swasthaiRenderAppNavLinks(activeSection) {
  return SWASTHAI_APP_NAV_LINKS.map(link => {
    const isActive = link.key === activeSection;
    return `<li><a href="${link.href}"${isActive ? ' class="active" aria-current="page"' : ''}>${link.label}</a></li>`;
  }).join('');
}

function swasthaiRenderAppHeader(activeSection) {
  const navLinks = swasthaiRenderAppNavLinks(activeSection);
  const user = (typeof swasthaiCurrentUser === 'function' && swasthaiCurrentUser()) || { name: 'there', email: '' };
  const avatarUrl = `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name)}&background=0F766E&color=fff`;

  return `
    <div class="app-header__container">
        <a href="dashboard.html" class="app-header__logo">Swasth<span class="text-primary">AI</span></a>

        <ul class="app-nav" id="appNav">${navLinks}</ul>

        <div class="app-header__actions">
            <div class="app-header__item">
                <button type="button" class="app-icon-btn" id="notifToggle" aria-haspopup="true" aria-expanded="false" aria-controls="notifPanel" aria-label="Notifications">
                    <i class="fas fa-bell"></i>
                </button>
                <div class="app-popover" id="notifPanel" role="region" aria-label="Notifications">
                    <div class="app-notif__header">Notifications</div>
                    <div class="app-notif__empty">
                        <i class="fas fa-bell-slash"></i>
                        <p>You're all caught up — no new notifications yet.</p>
                    </div>
                </div>
            </div>

            <div class="app-header__item">
                <button type="button" class="app-profile-btn" id="profileToggle" aria-haspopup="true" aria-expanded="false" aria-controls="profileMenu" aria-label="Open profile menu">
                    <img src="${avatarUrl}" alt="" class="avatar">
                    <span class="app-profile-btn__name">${user.name}</span>
                    <i class="fas fa-chevron-down"></i>
                </button>
                <div class="app-popover" id="profileMenu" role="menu" aria-label="Profile menu">
                    <div class="app-profile-menu__header">
                        <img src="${avatarUrl}" alt="" class="avatar">
                        <div><strong>${user.name}</strong><span>${user.email}</span></div>
                    </div>
                    <ul class="app-profile-menu__list">
                        <li role="none"><a role="menuitem" href="health-profile.html"><i class="fas fa-user-md"></i> Health Profile</a></li>
                        <li role="none"><a role="menuitem" href="medications.html"><i class="fas fa-pills"></i> Medications</a></li>
                        <li role="none"><a role="menuitem" href="medical-records.html"><i class="fas fa-folder-open"></i> Medical Records</a></li>
                    </ul>
                    <div class="app-profile-menu__divider"></div>
                    <ul class="app-profile-menu__list">
                        <li role="none"><a role="menuitem" class="is-danger" href="#" id="logoutLink"><i class="fas fa-sign-out-alt"></i> Log Out</a></li>
                    </ul>
                </div>
            </div>

            <button type="button" class="app-mobile-toggle" id="appMobileToggle" aria-label="Open navigation menu" aria-expanded="false" aria-controls="sidebar-container">
                <span></span><span></span><span></span>
            </button>
        </div>
    </div>`;
}

function swasthaiRenderAppDrawer(activeSection) {
  const navLinks = swasthaiRenderAppNavLinks(activeSection);

  return `
    <div class="navbar__drawer-header">
        <a href="dashboard.html" class="app-header__logo">Swasth<span class="text-primary">AI</span></a>
        <button type="button" class="navbar__drawer-close" id="appDrawerClose" aria-label="Close menu"><i class="fas fa-times"></i></button>
    </div>
    <ul class="navbar__drawer-links">${navLinks}</ul>
    <div class="navbar__drawer-actions">
        <a href="health-profile.html" class="btn btn-outline btn-block"><i class="fas fa-user-md"></i> Health Profile</a>
        <a href="#" class="btn btn-primary btn-block" id="drawerLogoutLink"><i class="fas fa-sign-out-alt"></i> Log Out</a>
    </div>`;
}

document.addEventListener('DOMContentLoaded', () => {
  const headerContainer = document.getElementById('header-container');
  const drawerContainer = document.getElementById('sidebar-container');
  if (!headerContainer && !drawerContainer) return;

  const activeSection = swasthaiCurrentAppSection();

  if (headerContainer) {
    headerContainer.innerHTML = swasthaiRenderAppHeader(activeSection);
  }
  if (drawerContainer) {
    // Deliberately NOT reusing nav.css's ".navbar__drawer" class here: main.js's
    // initMobileNav() queries that class globally, and app pages load main.js too,
    // which would double-wire this same drawer. ".app-drawer" avoids the collision
    // while still reusing the drawer's inner-content classes (header/links/actions)
    // and the shared .is-open / .navbar__overlay / body.drawer-open conventions.
    drawerContainer.classList.add('app-drawer');
    drawerContainer.innerHTML = swasthaiRenderAppDrawer(activeSection);
  }

  // Shared overlay backdrop for the mobile drawer (reuses nav.css's
  // .navbar__overlay, which app pages now also load).
  let overlay = document.getElementById('appDrawerOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'appDrawerOverlay';
    overlay.className = 'navbar__overlay';
    document.body.appendChild(overlay);
  }

  const mobileToggle = document.getElementById('appMobileToggle');
  const drawerClose = document.getElementById('appDrawerClose');
  const body = document.body;

  function openDrawer() {
    if (!drawerContainer) return;
    drawerContainer.classList.add('is-open');
    overlay.classList.add('is-open');
    body.classList.add('drawer-open');
    if (mobileToggle) mobileToggle.setAttribute('aria-expanded', 'true');
    const firstLink = drawerContainer.querySelector('a, button');
    if (firstLink) firstLink.focus();
  }

  function closeDrawer() {
    if (!drawerContainer) return;
    drawerContainer.classList.remove('is-open');
    overlay.classList.remove('is-open');
    body.classList.remove('drawer-open');
    if (mobileToggle) mobileToggle.setAttribute('aria-expanded', 'false');
    if (mobileToggle) mobileToggle.focus();
  }

  if (mobileToggle) {
    mobileToggle.addEventListener('click', () => {
      const isOpen = mobileToggle.getAttribute('aria-expanded') === 'true';
      isOpen ? closeDrawer() : openDrawer();
    });
  }
  if (drawerClose) drawerClose.addEventListener('click', closeDrawer);
  overlay.addEventListener('click', closeDrawer);

  if (drawerContainer) {
    drawerContainer.querySelectorAll('a').forEach(link => link.addEventListener('click', closeDrawer));
  }

  document.getElementById('logoutLink')?.addEventListener('click', (e) => {
    e.preventDefault();
    if (typeof swasthaiLogout === 'function') swasthaiLogout();
  });
  document.getElementById('drawerLogoutLink')?.addEventListener('click', (e) => {
    e.preventDefault();
    if (typeof swasthaiLogout === 'function') swasthaiLogout();
  });

  // Notifications + profile popovers — only one open at a time, close on
  // outside click or Escape.
  const popovers = [
    { toggle: document.getElementById('notifToggle'), panel: document.getElementById('notifPanel') },
    { toggle: document.getElementById('profileToggle'), panel: document.getElementById('profileMenu') }
  ].filter(p => p.toggle && p.panel);

  function closeAllPopovers(except) {
    popovers.forEach(({ toggle, panel }) => {
      if (panel === except) return;
      panel.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
    });
  }

  popovers.forEach(({ toggle, panel }) => {
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = panel.classList.contains('is-open');
      closeAllPopovers();
      if (!isOpen) {
        panel.classList.add('is-open');
        toggle.setAttribute('aria-expanded', 'true');
      }
    });
  });

  document.addEventListener('click', (e) => {
    const insidePopover = popovers.some(({ toggle, panel }) => toggle.contains(e.target) || panel.contains(e.target));
    if (!insidePopover) closeAllPopovers();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (drawerContainer && drawerContainer.classList.contains('is-open')) {
      closeDrawer();
      return;
    }
    closeAllPopovers();
  });
});
