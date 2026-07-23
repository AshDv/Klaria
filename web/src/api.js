let accessToken = localStorage.getItem("scribe_access_token");

export function setAccessToken(value) {
  accessToken = value;
  if (value) localStorage.setItem("scribe_access_token", value);
  else localStorage.removeItem("scribe_access_token");
}

export const isAuthenticated = () => Boolean(accessToken);

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let message = "Une erreur est survenue";
    try { message = (await response.json()).detail || message; } catch {}
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
  health: () => request("/api/health"),
  me: () => request("/api/auth/me"),
  legalNotices: () => request("/api/legal/notices"),
  acceptLegal: () => request("/api/legal/accept", {
    method: "POST",
    body: JSON.stringify({ terms_accepted: true, privacy_accepted: true }),
  }),
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
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!response.ok) throw new Error("E-mail ou mot de passe incorrect");
    const data = await response.json();
    setAccessToken(data.access_token);
  },
  createConsentSession: (data) => request("/api/consent-sessions", {
    method: "POST",
    body: JSON.stringify(data),
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
  listRecordings: () => request("/api/recordings"),
  getRecording: (id) => request(`/api/recordings/${id}`),
  createRecording: (title, audio, consent, consentSessionId) => {
    const form = new FormData();
    form.set("title", title);
    form.set("consent", String(consent));
    form.set("consent_session_id", consentSessionId);
    form.set("audio", audio, `scribe-${Date.now()}.webm`);
    return request("/api/recordings", { method: "POST", body: form });
  },
  deleteRecording: (id) => request(`/api/recordings/${id}`, { method: "DELETE" }),
};
