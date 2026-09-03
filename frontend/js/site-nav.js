/**
 * SwasthAI — Shared Site Navigation & Footer
 * Injects the same global header and footer into every page so the
 * multi-page site shares one consistent, reusable navigation system.
 * Must be included BEFORE main.js (which wires up scroll/drawer behavior
 * once this markup exists in the DOM).
 */

const SWASTHAI_NAV_LINKS = [
  { key: 'home', label: 'Home', href: 'index.html' },
  { key: 'how-it-works', label: 'How It Works', href: 'how-it-works.html' },
  { key: 'features', label: 'Services', href: 'features.html' },
  { key: 'about', label: 'About', href: 'about.html' }
];

function swasthaiRenderHeader(activePage) {
  const linksHtml = SWASTHAI_NAV_LINKS.map(link =>
    `<li><a href="${link.href}"${link.key === activePage ? ' class="active" aria-current="page"' : ''}>${link.label}</a></li>`
  ).join('');

  return `
    <nav class="navbar" id="navbar">
        <div class="navbar__container container">
            <a href="index.html" class="navbar__logo"><img src="assets/images/logo.png" alt="SwasthAI logo" class="logo-mark">Swasth<span class="text-primary">AI</span></a>
            <ul class="navbar__links" id="navLinks">${linksHtml}</ul>
            <div class="navbar__actions">
                <a href="login.html" class="btn btn-ghost${activePage === 'login' ? ' active' : ''}"${activePage === 'login' ? ' aria-current="page"' : ''}>Log In</a>
                <a href="register.html" class="btn btn-primary${activePage === 'register' ? ' active' : ''}"${activePage === 'register' ? ' aria-current="page"' : ''}>Get Started</a>
            </div>
            <button class="navbar__mobile-toggle" id="mobileToggle" aria-label="Open navigation menu" aria-expanded="false" aria-controls="navDrawer">
                <span></span><span></span><span></span>
            </button>
        </div>
        <div class="navbar__drawer" id="navDrawer">
            <div class="navbar__drawer-header">
                <a href="index.html" class="navbar__logo"><img src="assets/images/logo.png" alt="SwasthAI logo" class="logo-mark">Swasth<span class="text-primary">AI</span></a>
                <button class="navbar__drawer-close" id="drawerClose" aria-label="Close menu"><i class="fas fa-times"></i></button>
            </div>
            <ul class="navbar__drawer-links">${linksHtml}</ul>
            <div class="navbar__drawer-actions">
                <a href="login.html" class="btn btn-outline btn-block">Log In</a>
                <a href="register.html" class="btn btn-primary btn-block">Get Started</a>
            </div>
        </div>
        <div class="navbar__overlay" id="navOverlay"></div>
    </nav>`;
}

function swasthaiRenderFooter() {
  return `
    <footer class="footer">
        <div class="container">
            <div class="footer__grid">
                <div class="footer__brand">
                    <h3 class="footer__logo"><img src="assets/images/logo.png" alt="SwasthAI logo" class="logo-mark logo-mark--chip">Swasth<span style="color: var(--primary-light);">AI</span></h3>
                    <p>AI-powered personalized healthcare ecosystem. Understand, track and improve your health with intelligent technology.</p>
                    <div class="footer__social">
                        <a href="#" aria-label="Twitter"><i class="fab fa-twitter"></i></a>
                        <a href="#" aria-label="LinkedIn"><i class="fab fa-linkedin-in"></i></a>
                        <a href="#" aria-label="GitHub"><i class="fab fa-github"></i></a>
                    </div>
                </div>
                <div class="footer__col"><h4>Ecosystem</h4><ul>
                    <li><a href="ai-health.html">AI Health</a></li>
                    <li><a href="features.html">Features</a></li>
                    <li><a href="health-insights.html">Health Insights</a></li>
                    <li><a href="medical-records.html">Medical Records</a></li>
                    <li><a href="family.html">Family Health</a></li>
                </ul></div>
                <div class="footer__col"><h4>Healthcare</h4><ul>
                    <li><a href="doctors.html">Find a Doctor</a></li>
                    <li><a href="appointments.html">Appointments</a></li>
                    <li><a href="how-it-works.html">How It Works</a></li>
                    <li><a href="diet-lifestyle.html">Diet &amp; Lifestyle</a></li>
                    <li><a href="medications.html">Medications</a></li>
                </ul></div>
                <div class="footer__col"><h4>Company</h4><ul>
                    <li><a href="about.html">About SwasthAI</a></li>
                    <li><a href="register.html">Get Started</a></li>
                    <li><a href="login.html">Log In</a></li>
                    <li><a href="mailto:hello@swasthai.app">Contact</a></li>
                    <li><a href="privacy.html">Privacy Policy</a></li>
                    <li><a href="terms.html">Terms of Service</a></li>
                </ul></div>
            </div>
            <div class="footer__bottom">
                <p>2026 SwasthAI. All rights reserved.</p>
                <p class="footer__disclaimer"><i class="fas fa-info-circle"></i> SwasthAI provides AI-assisted health information and is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider.</p>
            </div>
        </div>
    </footer>`;
}

document.addEventListener('DOMContentLoaded', () => {
  const activePage = document.body.getAttribute('data-page') || '';

  const headerMount = document.getElementById('site-header');
  if (headerMount) {
    headerMount.outerHTML = swasthaiRenderHeader(activePage);
  }

  const footerMount = document.getElementById('site-footer');
  if (footerMount) {
    footerMount.outerHTML = swasthaiRenderFooter();
  }
});
