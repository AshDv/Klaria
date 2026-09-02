let accessToken = localStorage.getItem("klaria_access_token");
const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export function setAccessToken(value) {
  accessToken = value;
  if (value) localStorage.setItem("klaria_access_token", value);
  else localStorage.removeItem("klaria_access_token");
}

export const isAuthenticated = () => Boolean(accessToken);

export function remoteMeetingSocket(id) {
  const base = API_BASE || window.location.origin;
  const wsBase = base.replace(/^http/, "ws");
  return new WebSocket(`${wsBase}/api/remote-meetings/${id}/live`, ["klaria", accessToken]);
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let message = "Une erreur est survenue";
    try { message = (await response.json()).detail || message; } catch { /* réponse non JSON */ }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
  health: () => request("/api/health"),
  me: () => request("/api/auth/me"),
  register: async (fullName, email, password, termsAccepted, privacyAccepted) => {
    const data = await request("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({
        full_name: fullName,
        email,
        password,
        terms_accepted: termsAccepted,
        privacy_accepted: privacyAccepted,
      }),
    });
    setAccessToken(data.access_token);
  },
  login: async (email, password) => {
    const body = new URLSearchParams({ username: email, password });
    const response = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!response.ok) throw new Error("E-mail ou mot de passe incorrect");
    const data = await response.json();
    setAccessToken(data.access_token);
  },
  googleSsoUrl: () => `${API_BASE}/api/auth/sso/google`,
  microsoftSsoUrl: () => `${API_BASE}/api/auth/sso/microsoft`,
  calendarStatus: () => request("/api/calendars"),
  connectCalendar: (provider) => request(`/api/calendars/${provider}/connect`),
  syncCalendars: () => request("/api/calendars/sync", { method: "POST" }),
  calendarEvents: () => request("/api/calendar-events"),
  configureCalendarEvent: (id, enabled, options = {}) => request(`/api/calendar-events/${id}/automation`, {
    method: "PUT", body: JSON.stringify({ enabled, ...options }),
  }),
  disconnectCalendar: (id) => request(`/api/calendars/${id}`, { method: "DELETE" }),
  listRecordings: () => request("/api/recordings"),
  getRecording: (id) => request(`/api/recordings/${id}`),
  legalNotices: () => request("/api/legal/notices"),
  acceptLegal: () => request("/api/legal/accept", {
    method: "POST",
    body: JSON.stringify({ terms_accepted: true, privacy_accepted: true }),
  }),
  createConsentSession: (payload) => request("/api/consent-sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  listConsentSessions: () => request("/api/consent-sessions"),
  getConsentSession: (id) => request(`/api/consent-sessions/${id}`),
  startConsentSession: (id) => request(`/api/consent-sessions/${id}/start`, {
    method: "POST",
    body: JSON.stringify({ notice_confirmed: true }),
  }),
  stopConsentSession: (id) => request(`/api/consent-sessions/${id}/stop`, {
    method: "POST",
  }),
  getPublicConsent: (token) => request(`/api/public/consents/${token}`),
  acceptConsent: (token) => request(`/api/public/consents/${token}/accept`, {
    method: "POST",
  }),
  withdrawConsent: (token) => request(`/api/public/consents/${token}/withdraw`, {
    method: "POST",
  }),
  eraseConsentData: (token) => request(`/api/public/consents/${token}/data`, {
    method: "DELETE",
  }),
  getPublicReport: (token) => request(`/api/public/reports/${token}`),
  erasePublicReportData: (token) => request(`/api/public/reports/${token}/data`, {
    method: "DELETE",
  }),
  createRecording: (title, audio, consent, consentSessionId) => {
    const form = new FormData();
    form.set("title", title);
    form.set("consent", String(consent));
    form.set("consent_session_id", consentSessionId);
    form.set("audio", audio, `klaria-${Date.now()}.webm`);
    return request("/api/recordings", { method: "POST", body: form });
  },
  deleteRecording: (id) => request(`/api/recordings/${id}`, { method: "DELETE" }),
  createRemoteMeeting: (payload) => request("/api/remote-meetings", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  listRemoteMeetings: () => request("/api/remote-meetings"),
  getRemoteMeeting: (id) => request(`/api/remote-meetings/${id}`),
  getRemoteMeetingMedia: (id) => request(`/api/remote-meetings/${id}/media-access`),
  syncRemoteMeeting: (id) => request(`/api/remote-meetings/${id}/sync`, {
    method: "POST",
  }),
  finishRemoteMeeting: (id) => request(`/api/remote-meetings/${id}/finish`, {
    method: "POST",
  }),
  stopRemoteMeeting: (id) => request(`/api/remote-meetings/${id}/stop`, {
    method: "POST",
  }),
  createPodcast: (id, payload) => request(`/api/remote-meetings/${id}/podcast`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  reanalyzeRemoteMeeting: (id) => request(`/api/remote-meetings/${id}/reanalyze`, {
    method: "POST",
  }),
  updateMeetingAction: (id, index, payload) => request(`/api/remote-meetings/${id}/actions/${index}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  }),
  shareMeetingReport: (id, recipientEmails) => request(`/api/remote-meetings/${id}/share`, {
    method: "POST",
    body: JSON.stringify({ recipient_emails:recipientEmails }),
  }),
  createMeetingFollowUp: (id, payload) => request(`/api/remote-meetings/${id}/follow-up`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  deleteRemoteMeeting: (id) => request(`/api/remote-meetings/${id}`, {
    method: "DELETE",
  }),
  workspaceOverview: () => request("/api/workspace/overview"),
  exportData: () => request("/api/privacy/export"),
  deleteAccount: () => request("/api/privacy/account", {
    method: "DELETE",
    body: JSON.stringify({ confirmation: "DELETE" }),
  }),
};
