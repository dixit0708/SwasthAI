/**
 * SwasthAI — Expanding cards (hover/focus/tap to expand).
 * Vanilla port of a grid-based expanding-card interaction: the active
 * card grows to 5fr while the rest sit at 1fr, columns on desktop and
 * rows on narrow screens.
 */
(function () {
  function init() {
    const list = document.getElementById('expandingCards');
    if (!list) return;

    const cards = Array.from(list.querySelectorAll('.expanding-card'));
    if (!cards.length) return;

    let activeIndex = cards.findIndex(card => card.dataset.active === 'true');
    if (activeIndex === -1) activeIndex = 0;

    function isDesktop() {
      return window.innerWidth >= 768;
    }

    function applyLayout() {
      const track = cards.map((_, i) => (i === activeIndex ? '5fr' : '1fr')).join(' ');
      if (isDesktop()) {
        list.style.gridTemplateColumns = track;
        list.style.gridTemplateRows = '1fr';
      } else {
        list.style.gridTemplateRows = track;
        list.style.gridTemplateColumns = '1fr';
      }
      cards.forEach((card, i) => {
        card.dataset.active = i === activeIndex ? 'true' : 'false';
      });
    }

    function setActive(index) {
      if (index === activeIndex) return;
      activeIndex = index;
      applyLayout();
    }

    cards.forEach((card, index) => {
      card.addEventListener('mouseenter', () => setActive(index));
      card.addEventListener('focus', () => setActive(index));
      card.addEventListener('click', () => setActive(index));
    });

    window.addEventListener('resize', applyLayout, { passive: true });
    applyLayout();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
