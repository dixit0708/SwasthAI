/**
 * SwasthAI — Auth API client and session helpers.
 * Talks to the FastAPI backend's JWT auth endpoints and keeps the
 * session (token + user) in localStorage for every page to read.
 */

const SWASTHAI_API_BASE = 'http://127.0.0.1:8000/api/v1';
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
    throw new Error(data.detail || 'Something went wrong. Please try again.');
  }
  return data;
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
