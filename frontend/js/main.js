/**
 * SwasthAI Landing Page JavaScript
 * Clean Vanilla JS implementation
 */

// === Utility functions ===

// Check if user prefers reduced motion
const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Easing function for smooth animations (easeOutExpo)
const easeOutExpo = (t) => t === 1 ? 1 : 1 - Math.pow(2, -10 * t);

// === Navbar ===
function initNavbar() {
  const navbar = document.querySelector('.navbar');
  if (!navbar) return;

  // Use passive event listener for performance
  window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
      navbar.classList.add('navbar--scrolled');
    } else {
      navbar.classList.remove('navbar--scrolled');
    }
  }, { passive: true });
}

// === Mobile Navigation ===
function initMobileNav() {
  const toggleBtn = document.querySelector('.navbar__mobile-toggle');
  const drawer = document.querySelector('.navbar__drawer');
  const overlay = document.querySelector('.navbar__overlay');
  const closeBtn = document.querySelector('.navbar__drawer-close');
  const body = document.body;

  if (!toggleBtn || !drawer) return;
  
  const focusableElements = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
  const firstFocusableElement = drawer.querySelectorAll(focusableElements)[0];
  const focusableContent = drawer.querySelectorAll(focusableElements);
  const lastFocusableElement = focusableContent[focusableContent.length - 1];

  function openDrawer() {
    drawer.classList.add('is-open');
    if (overlay) overlay.classList.add('is-open');
    body.classList.add('drawer-open');
    toggleBtn.setAttribute('aria-expanded', 'true');
    // Set focus to the first element when opened
    if (firstFocusableElement) firstFocusableElement.focus();
  }

  function closeDrawer() {
    drawer.classList.remove('is-open');
    if (overlay) overlay.classList.remove('is-open');
    body.classList.remove('drawer-open');
    toggleBtn.setAttribute('aria-expanded', 'false');
    toggleBtn.focus();
  }

  toggleBtn.addEventListener('click', () => {
    const isExpanded = toggleBtn.getAttribute('aria-expanded') === 'true';
    if (isExpanded) {
      closeDrawer();
    } else {
      openDrawer();
    }
  });

  if (overlay) {
    overlay.addEventListener('click', closeDrawer);
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', closeDrawer);
  }

  // Close when clicking a link inside
  const drawerLinks = drawer.querySelectorAll('a');
  drawerLinks.forEach(link => {
    link.addEventListener('click', closeDrawer);
  });

  // Keyboard navigation & Escape handling
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && drawer.classList.contains('is-open')) {
      closeDrawer();
    }
    
    // Trap focus inside drawer when open
    if (e.key === 'Tab' && drawer.classList.contains('is-open')) {
      if (e.shiftKey) { // if shift key pressed for shift + tab
        if (document.activeElement === firstFocusableElement) {
          lastFocusableElement.focus();
          e.preventDefault();
        }
      } else { // if tab key is pressed
        if (document.activeElement === lastFocusableElement) {
          firstFocusableElement.focus();
          e.preventDefault();
        }
      }
    }
  });
}

// === Smooth Scrolling ===
function initSmoothScroll() {
  const links = document.querySelectorAll('a[href^="#"]');
  const navbarHeight = 70; // Fixed navbar height

  links.forEach(link => {
    link.addEventListener('click', function(e) {
      const targetId = this.getAttribute('href');
      
      // Skip if just "#"
      if (targetId === '#') return;
      
      const targetElement = document.querySelector(targetId);
      
      if (targetElement) {
        e.preventDefault();
        const elementPosition = targetElement.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - navbarHeight;

        window.scrollTo({
          top: offsetPosition,
          behavior: prefersReducedMotion() ? 'auto' : 'smooth'
        });
      }
    });
  });
}

// === Scroll Animations ===
function initScrollAnimations() {
  if (prefersReducedMotion()) {
    // If reduced motion is preferred, make all elements visible immediately
    document.querySelectorAll('.animate-on-scroll').forEach(el => {
      el.classList.add('is-visible');
      el.style.transition = 'none';
      el.style.animation = 'none';
    });
    return;
  }

  const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.15
  };

  const scrollObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const el = entry.target;
        
        // Handle staggered delay if provided via data attribute
        const delay = el.getAttribute('data-delay');
        if (delay) {
          el.style.transitionDelay = `${delay}ms`;
          el.style.animationDelay = `${delay}ms`;
        }
        
        el.classList.add('is-visible');
        observer.unobserve(el); // Only animate once
      }
    });
  }, observerOptions);

  document.querySelectorAll('.animate-on-scroll').forEach(el => {
    scrollObserver.observe(el);
  });
}

// === Counter Animation ===
function initCounters() {
  if (prefersReducedMotion()) {
    // Just set immediately
    document.querySelectorAll('.counter').forEach(counter => {
      const target = parseFloat(counter.getAttribute('data-target'));
      const suffix = counter.getAttribute('data-suffix') || '';
      counter.innerText = target + suffix;
    });
    return;
  }

  const duration = 2000; // 2 seconds

  const counterObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const counter = entry.target;
        const target = parseFloat(counter.getAttribute('data-target'));
        const suffix = counter.getAttribute('data-suffix') || '';
        let startTime = null;

        const animate = (currentTime) => {
          if (!startTime) startTime = currentTime;
          const progress = currentTime - startTime;
          const percent = Math.min(progress / duration, 1);
          const currentVal = target * easeOutExpo(percent);

          // Format depending on if it's integer or float
          if (target % 1 === 0) {
            counter.innerText = Math.floor(currentVal) + suffix;
          } else {
            counter.innerText = currentVal.toFixed(1) + suffix;
          }

          if (progress < duration) {
            requestAnimationFrame(animate);
          } else {
            counter.innerText = target + suffix;
          }
        };

        requestAnimationFrame(animate);
        observer.unobserve(counter);
      }
    });
  }, { threshold: 0.5 });

  document.querySelectorAll('.counter').forEach(counter => {
    counterObserver.observe(counter);
  });
}

// === Initialize ===
document.addEventListener('DOMContentLoaded', () => {
  initNavbar();
  initMobileNav();
  initSmoothScroll();
  initScrollAnimations();
  initCounters();
});
