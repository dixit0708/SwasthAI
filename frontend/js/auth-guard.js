/**
 * SwasthAI — Page guard for authenticated app pages.
 * Runs synchronously before the rest of the page renders. Redirects
 * to login.html if there is no session token, or if the token's own
 * expiry has passed. The backend independently re-validates the
 * token on every API call — this is a UX guard, not the security
 * boundary.
 */
(function () {
  function isTokenValid(token) {
    if (!token) return false;
    try {
      const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
      return typeof payload.exp === 'number' && payload.exp * 1000 > Date.now();
    } catch (err) {
      return false;
    }
  }

  const token = localStorage.getItem('swasthai_token');
  if (!isTokenValid(token)) {
    localStorage.removeItem('swasthai_token');
    localStorage.removeItem('swasthai_user');
    const page = window.location.pathname.split('/').pop();
    window.location.replace(`login.html?next=${encodeURIComponent(page)}`);
  }
})();
