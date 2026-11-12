/**
 * SwasthAI — Authenticated app header, mobile nav drawer,
 * notifications panel and profile menu.
 * Injects into #header-container (top app header) and reuses
 * #sidebar-container as an off-canvas mobile nav drawer.
 */

const SWASTHAI_APP_NAV_LINKS = [
  { key: 'dashboard', label: 'Dashboard', href: 'dashboard.html' },
  {
    key: 'my-health',
    label: 'My Health',
    href: 'health-profile.html',
    subnav: [
      { label: 'Health Profile',    href: 'health-profile.html',  icon: 'fa-user-md' },
      { label: 'Diet & Lifestyle',  href: 'diet-lifestyle.html',  icon: 'fa-apple-whole' },
      { label: 'Medications',       href: 'medications.html',     icon: 'fa-pills' },
      { label: 'Medical Records',   href: 'medical-records.html', icon: 'fa-folder-open' },
    ]
  },
  {
    key: 'ai-insights',
    label: 'AI Insights',
    href: 'predictions.html',
    subnav: [
      { label: 'Health Risk Predictions', href: 'predictions.html',   icon: 'fa-chart-line' },
      { label: 'AI Assistant',            href: 'ai-assistant.html',  icon: 'fa-robot' },
      { label: 'Report Analyzer',         href: 'report-analyzer.html', icon: 'fa-file-medical' },
    ]
  },
  { key: 'family',  label: 'Family',  href: 'family.html' },
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
  'prediction-diabetes-choose.html': 'ai-insights',
  'prediction-diabetes-pima.html': 'ai-insights',
  'prediction-heart.html': 'ai-insights',
  'prediction-liver.html': 'ai-insights',
  'prediction-liver-choose.html': 'ai-insights',
  'prediction-liver-ilpd.html': 'ai-insights',
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
    if (link.subnav && link.subnav.length) {
      const items = link.subnav.map(sub =>
        `<li><a href="${sub.href}"${sub.href === (window.location.pathname.split('/').pop() || '') ? ' class="active"' : ''}>
           <i class="fas ${sub.icon}" aria-hidden="true"></i> ${sub.label}
         </a></li>`
      ).join('');
      return `
        <li class="app-nav__has-dropdown${isActive ? ' is-active' : ''}">
          <a href="${link.href}"${isActive ? ' class="active" aria-current="page"' : ''}
             aria-haspopup="true" aria-expanded="false">
            ${link.label} <i class="fas fa-chevron-down app-nav__caret" aria-hidden="true"></i>
          </a>
          <ul class="app-nav__dropdown" role="menu">${items}</ul>
        </li>`;
    }
    return `<li><a href="${link.href}"${isActive ? ' class="active" aria-current="page"' : ''}>${link.label}</a></li>`;
  }).join('');
}

function swasthaiInjectNavDropdownStyles() {
  if (document.getElementById('swasthai-nav-dropdown-styles')) return;
  const style = document.createElement('style');
  style.id = 'swasthai-nav-dropdown-styles';
  style.textContent = `
    /* ── Nav dropdown ─────────────────────────────────────────────── */
    .app-nav__has-dropdown { position: relative; }
    .app-nav__caret {
      font-size: 0.65em;
      margin-left: 0.3rem;
      transition: transform 0.2s ease;
      vertical-align: middle;
    }
    .app-nav__has-dropdown:hover .app-nav__caret,
    .app-nav__has-dropdown:focus-within .app-nav__caret {
      transform: rotate(180deg);
    }
    .app-nav__dropdown {
      display: none;
      position: absolute;
      top: calc(100% + 6px);
      left: 50%;
      transform: translateX(-50%);
      min-width: 210px;
      background: #fff;
      border: 1px solid var(--border, #e2e8f0);
      border-radius: 10px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.10);
      list-style: none;
      margin: 0;
      padding: 0.4rem 0;
      z-index: 9999;
      animation: navDropIn 0.15s ease;
    }
    @keyframes navDropIn {
      from { opacity: 0; transform: translateX(-50%) translateY(-6px); }
      to   { opacity: 1; transform: translateX(-50%) translateY(0); }
    }
    .app-nav__has-dropdown:hover .app-nav__dropdown,
    .app-nav__has-dropdown:focus-within .app-nav__dropdown {
      display: block;
    }
    .app-nav__dropdown li a {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      padding: 0.55rem 1.1rem;
      font-size: 0.88rem;
      color: var(--text-primary, #1e293b);
      white-space: nowrap;
      text-decoration: none;
      border-radius: 0;
      transition: background 0.15s, color 0.15s;
    }
    .app-nav__dropdown li a:hover,
    .app-nav__dropdown li a.active {
      background: var(--bg-surface-alt, #f1f5f9);
      color: var(--primary, #0f766e);
    }
    .app-nav__dropdown li a i { width: 1rem; text-align: center; opacity: 0.75; }
    /* small separator between dropdown groups if needed */
    .app-nav__dropdown li + li { border-top: 1px solid var(--border, #e2e8f0); }
    /* ─────────────────────────────────────────────────────────────── */
  `;
  document.head.appendChild(style);
}

function swasthaiRenderAppHeader(activeSection) {
  const navLinks = swasthaiRenderAppNavLinks(activeSection);
  const user = (typeof swasthaiCurrentUser === 'function' && swasthaiCurrentUser()) || { name: 'there', email: '' };
  const avatarUrl = `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name)}&background=0F766E&color=fff`;

  return `
    <div class="app-header__container">
        <a href="dashboard.html" class="app-header__logo"><img src="assets/images/logo.png" alt="SwasthAI logo" class="logo-mark">Swasth<span class="text-primary">AI</span></a>

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
                        <li role="none"><a role="menuitem" href="diet-lifestyle.html"><i class="fas fa-apple-whole"></i> Diet &amp; Lifestyle</a></li>
                        <li role="none"><a role="menuitem" href="family.html"><i class="fas fa-user-friends"></i> Family Records</a></li>
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
  // For mobile drawer, render a flat list that includes subnav items inline.
  const allLinks = SWASTHAI_APP_NAV_LINKS.flatMap(link => {
    const topItem = `<li><a href="${link.href}"${link.key === activeSection ? ' class="active"' : ''}>${link.label}</a></li>`;
    if (!link.subnav) return [topItem];
    const subItems = link.subnav.map(sub =>
      `<li style="padding-left:1rem;"><a href="${sub.href}" style="font-size:0.9em;opacity:0.85;"><i class="fas ${sub.icon}" style="width:1rem;"></i> ${sub.label}</a></li>`
    );
    return [topItem, ...subItems];
  }).join('');

  return `
    <div class="navbar__drawer-header">
        <a href="dashboard.html" class="app-header__logo"><img src="assets/images/logo.png" alt="SwasthAI logo" class="logo-mark">Swasth<span class="text-primary">AI</span></a>
        <button type="button" class="navbar__drawer-close" id="appDrawerClose" aria-label="Close menu"><i class="fas fa-times"></i></button>
    </div>
    <ul class="navbar__drawer-links">${allLinks}</ul>
    <div class="navbar__drawer-actions">
        <a href="health-profile.html" class="btn btn-outline btn-block"><i class="fas fa-user-md"></i> Health Profile</a>
        <a href="#" class="btn btn-primary btn-block" id="drawerLogoutLink"><i class="fas fa-sign-out-alt"></i> Log Out</a>
    </div>`;
}

document.addEventListener('DOMContentLoaded', () => {
  const headerContainer = document.getElementById('header-container');
  const drawerContainer = document.getElementById('sidebar-container');
  if (!headerContainer && !drawerContainer) return;

  // Inject dropdown CSS before rendering.
  swasthaiInjectNavDropdownStyles();

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
