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
    },
    liver(payload) {
      return swasthaiAuthedRequest('/predict/liver', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    },
    liverLifestyle(payload) {
      return swasthaiAuthedRequest('/predict/liver-lifestyle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    },
    // No Content-Type header here on purpose: the browser sets
    // multipart/form-data with the correct boundary itself when the body
    // is a FormData instance. The pneumonia endpoint doesn't require auth
    // (it isn't tied to a user record the way diabetes predictions are),
    // so this uses the unauthenticated request helper.
    pneumonia(file) {
      const formData = new FormData();
      formData.append('file', file);
      return swasthaiApiRequest('/predict/pneumonia', {
        method: 'POST',
        body: formData
      });
    }
  },
  family: {
    getOverview() {
      return swasthaiAuthedRequest('/family/overview');
    },
    listMembers(includeArchived = false) {
      return swasthaiAuthedRequest(`/family/members?include_archived=${includeArchived}`);
    },
    getMember(id) {
      return swasthaiAuthedRequest(`/family/members/${encodeURIComponent(id)}`);
    },
    createMember(payload) {
      return swasthaiAuthedRequest('/family/members', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    },
    updateMember(id, payload) {
      return swasthaiAuthedRequest(`/family/members/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    },
    deleteMember(id, cascade = true) {
      return swasthaiAuthedRequest(`/family/members/${encodeURIComponent(id)}?cascade=${cascade}`, {
        method: 'DELETE'
      });
    },
    addHistory(memberId, payload) {
      return swasthaiAuthedRequest(`/family/members/${encodeURIComponent(memberId)}/history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    },
    updateHistory(memberId, itemId, payload) {
      return swasthaiAuthedRequest(`/family/members/${encodeURIComponent(memberId)}/history/${encodeURIComponent(itemId)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    },
    deleteHistory(memberId, itemId) {
      return swasthaiAuthedRequest(`/family/members/${encodeURIComponent(memberId)}/history/${encodeURIComponent(itemId)}`, {
        method: 'DELETE'
      });
    },
    listRecords(params = {}) {
      const qs = new URLSearchParams();
      if (params.memberId) qs.append('member_id', params.memberId);
      if (params.category) qs.append('category', params.category);
      if (params.search) qs.append('search', params.search);
      if (params.startDate) qs.append('start_date', params.startDate);
      if (params.endDate) qs.append('end_date', params.endDate);
      if (params.sort) qs.append('sort', params.sort);
      const query = qs.toString() ? `?${qs.toString()}` : '';
      return swasthaiAuthedRequest(`/family/records${query}`);
    },
    createRecord(formData) {
      const token = swasthaiGetToken();
      return swasthaiApiRequest('/family/records', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData
      });
    },
    getRecord(id) {
      return swasthaiAuthedRequest(`/family/records/${encodeURIComponent(id)}`);
    },
    updateRecord(id, payload) {
      return swasthaiAuthedRequest(`/family/records/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    },
    deleteRecord(id) {
      return swasthaiAuthedRequest(`/family/records/${encodeURIComponent(id)}`, {
        method: 'DELETE'
      });
    },
    getDocumentDownloadUrl(recordId, download = false) {
      const token = swasthaiGetToken();
      return `${SWASTHAI_API_BASE}/family/records/${encodeURIComponent(recordId)}/document${download ? '?download=true' : ''}`;
    },
    async fetchDocumentBlob(recordId) {
      const token = swasthaiGetToken();
      const res = await fetch(`${SWASTHAI_API_BASE}/family/records/${encodeURIComponent(recordId)}/document`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Failed to load document');
      return await res.blob();
    },
    listMedications(params = {}) {
      const qs = new URLSearchParams();
      if (params.memberId) qs.append('member_id', params.memberId);
      if (params.status) qs.append('status', params.status);
      const query = qs.toString() ? `?${qs.toString()}` : '';
      return swasthaiAuthedRequest(`/family/medications${query}`);
    },
    createMedication(payload) {
      return swasthaiAuthedRequest('/family/medications', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    },
    updateMedication(id, payload) {
      return swasthaiAuthedRequest(`/family/medications/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    },
    deleteMedication(id) {
      return swasthaiAuthedRequest(`/family/medications/${encodeURIComponent(id)}`, {
        method: 'DELETE'
      });
    },
    listMeasurements(params = {}) {
      const qs = new URLSearchParams();
      if (params.memberId) qs.append('member_id', params.memberId);
      if (params.metricType) qs.append('metric_type', params.metricType);
      const query = qs.toString() ? `?${qs.toString()}` : '';
      return swasthaiAuthedRequest(`/family/measurements${query}`);
    },
    createMeasurement(payload) {
      return swasthaiAuthedRequest('/family/measurements', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    },
    deleteMeasurement(id) {
      return swasthaiAuthedRequest(`/family/measurements/${encodeURIComponent(id)}`, {
        method: 'DELETE'
      });
    },
    getTimeline(memberId = null) {
      const query = memberId ? `?member_id=${encodeURIComponent(memberId)}` : '';
      return swasthaiAuthedRequest(`/family/timeline${query}`);
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
