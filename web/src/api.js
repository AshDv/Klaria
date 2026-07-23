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
};
