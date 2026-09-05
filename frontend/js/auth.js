/**
 * SwasthAI — Auth API client and session helpers.
 * Talks to the FastAPI backend's JWT auth endpoints and keeps the
 * session (token + user) in localStorage for every page to read.
 */

// Auto-detects local dev vs. the deployed site so the same file works in
// both places without a build step or manual toggling (PRD Section 7.7 /
// 28: centralized API config, never a hardcoded URL per environment).
const SWASTHAI_API_BASE = (() => {
  const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
  return isLocal
    ? 'http://127.0.0.1:8000/api/v1'
    : 'https://swasthai-slac.onrender.com/api/v1';
})();
const SWASTHAI_TOKEN_KEY = 'swasthai_token';
const SWASTHAI_USER_KEY = 'swasthai_user';

async function swasthaiApiRequest(path, options) {
  let res;
  try {
    res = await fetch(`${SWASTHAI_API_BASE}${path}`, options);
  } catch (err) {
    throw new Error('Could not reach the SwasthAI server. Please try again.');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const error = new Error(data.detail || 'Something went wrong. Please try again.');
    error.status = res.status;
    throw error;
  }
  return data;
}

/**
 * For calls that require the logged-in user's session. Attaches the
 * bearer token automatically and, per the error-handling standard (only
 * a genuine 401 means "you are not authenticated"), logs the user out
 * on 401 only — 403/404/422/500/etc. are left for the caller to handle
 * as their own error state, never as a forced logout.
 */
async function swasthaiAuthedRequest(path, options = {}) {
  const token = swasthaiGetToken();
  try {
    return await swasthaiApiRequest(path, {
      ...options,
      headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` }
    });
  } catch (err) {
    if (err.status === 401 && typeof swasthaiLogout === 'function') {
      swasthaiLogout();
    }
    throw err;
  }
}

const SwasthAPI = {
  register(name, email, password) {
    return swasthaiApiRequest('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password })
    });
  },
  login(email, password) {
    return swasthaiApiRequest('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
  },
  me(token) {
    return swasthaiApiRequest('/auth/me', {
      headers: { Authorization: `Bearer ${token}` }
    });
  },
  healthProfile: {
    get() {
      return swasthaiAuthedRequest('/health-profile/me');
    },
    update({ date_of_birth, blood_group }) {
      return swasthaiAuthedRequest('/health-profile/me', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date_of_birth: date_of_birth || null, blood_group: blood_group || null })
      });
    },
    addCondition(label) {
      return swasthaiAuthedRequest('/health-profile/me/conditions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label })
      });
    },
    deleteCondition(conditionId) {
      return swasthaiAuthedRequest(`/health-profile/me/conditions/${encodeURIComponent(conditionId)}`, {
        method: 'DELETE'
      });
    }
  },
  predictions: {
    diabetes(payload) {
      return swasthaiAuthedRequest('/predict/diabetes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    }
  }
};

function swasthaiStoreSession(data) {
  localStorage.setItem(SWASTHAI_TOKEN_KEY, data.access_token);
  localStorage.setItem(SWASTHAI_USER_KEY, JSON.stringify(data.user));
}

function swasthaiClearSession() {
  localStorage.removeItem(SWASTHAI_TOKEN_KEY);
  localStorage.removeItem(SWASTHAI_USER_KEY);
}

function swasthaiGetToken() {
  return localStorage.getItem(SWASTHAI_TOKEN_KEY);
}

function swasthaiCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem(SWASTHAI_USER_KEY));
  } catch (err) {
    return null;
  }
}

function swasthaiLogout() {
  swasthaiClearSession();
  window.location.href = 'login.html';
}

window.SwasthAPI = SwasthAPI;
window.swasthaiStoreSession = swasthaiStoreSession;
window.swasthaiClearSession = swasthaiClearSession;
window.swasthaiGetToken = swasthaiGetToken;
window.swasthaiCurrentUser = swasthaiCurrentUser;
window.swasthaiLogout = swasthaiLogout;
