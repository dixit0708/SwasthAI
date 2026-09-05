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
  'assets/images/dashboard-hero/hero-1.jpg',
  'assets/images/dashboard-hero/hero-2.jpg',
  'assets/images/dashboard-hero/hero-3.jpg',
  'assets/images/dashboard-hero/hero-4.jpg',
  'assets/images/dashboard-hero/hero-5.jpg',
  'assets/images/dashboard-hero/hero-6.jpg',
  'assets/images/dashboard-hero/hero-7.jpg',
  'assets/images/dashboard-hero/hero-8.jpg',
  'assets/images/dashboard-hero/hero-9.jpg',
  'assets/images/dashboard-hero/hero-10.jpg',
  'assets/images/dashboard-hero/hero-11.jpg',
  'assets/images/dashboard-hero/hero-12.jpg',
  'assets/images/dashboard-hero/hero-13.jpg',
  'assets/images/dashboard-hero/hero-14.jpg',
  'assets/images/dashboard-hero/hero-15.jpg'
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
