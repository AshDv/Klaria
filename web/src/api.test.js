import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

async function loadApi() {
  vi.resetModules();
  return import("./api");
}

describe("client API", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => vi.unstubAllGlobals());

  it("stocke et retire le jeton d'accès", async () => {
    const { isAuthenticated, setAccessToken } = await loadApi();
    setAccessToken("secret");
    expect(isAuthenticated()).toBe(true);
    expect(localStorage.getItem("klaria_access_token")).toBe("secret");
    setAccessToken(null);
    expect(isAuthenticated()).toBe(false);
    expect(localStorage.getItem("klaria_access_token")).toBeNull();
  });

  it("ajoute le bearer token et sérialise le JSON", async () => {
    const { api, setAccessToken } = await loadApi();
    setAccessToken("token-test");
    fetch.mockResolvedValue({ ok: true, status: 200, json: vi.fn().mockResolvedValue({ id: "m1" }) });
    await api.createRemoteMeeting({ title: "Démo" });
    const [, options] = fetch.mock.calls[0];
    expect(options.method).toBe("POST");
    expect(options.headers.get("Authorization")).toBe("Bearer token-test");
    expect(options.headers.get("Content-Type")).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual({ title: "Démo" });
  });

  it("retourne null pour une réponse 204", async () => {
    const { api } = await loadApi();
    fetch.mockResolvedValue({ ok: true, status: 204 });
    await expect(api.deleteRecording("r1")).resolves.toBeNull();
  });

  it("remonte le détail JSON d'une erreur HTTP", async () => {
    const { api } = await loadApi();
    fetch.mockResolvedValue({ ok: false, status: 403, json: vi.fn().mockResolvedValue({ detail: "Accès refusé" }) });
    await expect(api.me()).rejects.toThrow("Accès refusé");
  });

  it("utilise un message sûr si l'erreur n'est pas JSON", async () => {
    const { api } = await loadApi();
    fetch.mockResolvedValue({ ok: false, status: 500, json: vi.fn().mockRejectedValue(new Error("html")) });
    await expect(api.health()).rejects.toThrow("Une erreur est survenue");
  });

  it("construit le WebSocket sécurisé avec le jeton", async () => {
    const socket = vi.fn();
    vi.stubGlobal("WebSocket", socket);
    const { remoteMeetingSocket, setAccessToken } = await loadApi();
    setAccessToken("ws-token");
    remoteMeetingSocket("meeting 1");
    expect(socket).toHaveBeenCalledWith(expect.stringMatching(/^ws.*\/api\/remote-meetings\/meeting 1\/live$/), ["klaria", "ws-token"]);
  });

  const endpoints = [
    ["health", [], "/api/health", "GET"],
    ["me", [], "/api/auth/me", "GET"],
    ["calendarStatus", [], "/api/calendars", "GET"],
    ["connectCalendar", ["google"], "/api/calendars/google/connect", "GET"],
    ["syncCalendars", [], "/api/calendars/sync", "POST"],
    ["calendarEvents", [], "/api/calendar-events", "GET"],
    ["configureCalendarEvent", ["e1", true, { notify: true }], "/api/calendar-events/e1/automation", "PUT"],
    ["disconnectCalendar", ["c1"], "/api/calendars/c1", "DELETE"],
    ["listRecordings", [], "/api/recordings", "GET"],
    ["getRecording", ["r1"], "/api/recordings/r1", "GET"],
    ["legalNotices", [], "/api/legal/notices", "GET"],
    ["acceptLegal", [], "/api/legal/accept", "POST"],
    ["createConsentSession", [{ title: "Réunion" }], "/api/consent-sessions", "POST"],
    ["listConsentSessions", [], "/api/consent-sessions", "GET"],
    ["getConsentSession", ["s1"], "/api/consent-sessions/s1", "GET"],
    ["startConsentSession", ["s1"], "/api/consent-sessions/s1/start", "POST"],
    ["stopConsentSession", ["s1"], "/api/consent-sessions/s1/stop", "POST"],
    ["getPublicConsent", ["t1"], "/api/public/consents/t1", "GET"],
    ["acceptConsent", ["t1"], "/api/public/consents/t1/accept", "POST"],
    ["withdrawConsent", ["t1"], "/api/public/consents/t1/withdraw", "POST"],
    ["eraseConsentData", ["t1"], "/api/public/consents/t1/data", "DELETE"],
    ["getPublicReport", ["t1"], "/api/public/reports/t1", "GET"],
    ["erasePublicReportData", ["t1"], "/api/public/reports/t1/data", "DELETE"],
    ["deleteRecording", ["r1"], "/api/recordings/r1", "DELETE"],
    ["listRemoteMeetings", [], "/api/remote-meetings", "GET"],
    ["getRemoteMeeting", ["m1"], "/api/remote-meetings/m1", "GET"],
    ["getRemoteMeetingMedia", ["m1"], "/api/remote-meetings/m1/media-access", "GET"],
    ["syncRemoteMeeting", ["m1"], "/api/remote-meetings/m1/sync", "POST"],
    ["finishRemoteMeeting", ["m1"], "/api/remote-meetings/m1/finish", "POST"],
    ["stopRemoteMeeting", ["m1"], "/api/remote-meetings/m1/stop", "POST"],
    ["createPodcast", ["m1", { minutes: 5 }], "/api/remote-meetings/m1/podcast", "POST"],
    ["reanalyzeRemoteMeeting", ["m1"], "/api/remote-meetings/m1/reanalyze", "POST"],
    ["updateMeetingAction", ["m1", 2, { done: true }], "/api/remote-meetings/m1/actions/2", "PUT"],
    ["shareMeetingReport", ["m1", ["a@example.test"]], "/api/remote-meetings/m1/share", "POST"],
    ["createMeetingFollowUp", ["m1", { title: "Suivi" }], "/api/remote-meetings/m1/follow-up", "POST"],
    ["deleteRemoteMeeting", ["m1"], "/api/remote-meetings/m1", "DELETE"],
    ["workspaceOverview", [], "/api/workspace/overview", "GET"],
    ["exportData", [], "/api/privacy/export", "GET"],
    ["deleteAccount", [], "/api/privacy/account", "DELETE"],
  ];

  it.each(endpoints)("%s appelle la bonne route", async (name, args, path, method) => {
    const { api } = await loadApi();
    fetch.mockResolvedValue({ ok: true, status: 200, json: vi.fn().mockResolvedValue({ ok: true }) });
    await api[name](...args);
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe(path);
    expect(options.method || "GET").toBe(method);
  });

  it("expose les routes SSO", async () => {
    const { api } = await loadApi();
    expect(api.googleSsoUrl()).toBe("/api/auth/sso/google");
    expect(api.microsoftSsoUrl()).toBe("/api/auth/sso/microsoft");
  });

  it("enregistre puis connecte un utilisateur", async () => {
    const { api } = await loadApi();
    fetch
      .mockResolvedValueOnce({ ok: true, status: 200, json: vi.fn().mockResolvedValue({ access_token: "register-token" }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: vi.fn().mockResolvedValue({ access_token: "login-token" }) });
    await api.register("Ada", "ada@example.test", "mot-de-passe", true, true);
    expect(localStorage.getItem("klaria_access_token")).toBe("register-token");
    await api.login("ada@example.test", "mot-de-passe");
    expect(localStorage.getItem("klaria_access_token")).toBe("login-token");
  });

  it("rejette des identifiants invalides", async () => {
    const { api } = await loadApi();
    fetch.mockResolvedValue({ ok: false, status: 401 });
    await expect(api.login("x@example.test", "incorrect")).rejects.toThrow("E-mail ou mot de passe incorrect");
  });

  it("envoie un enregistrement sous forme multipart", async () => {
    const { api } = await loadApi();
    fetch.mockResolvedValue({ ok: true, status: 200, json: vi.fn().mockResolvedValue({ id: "r1" }) });
    await api.createRecording("Démo", new Blob(["audio"], { type: "audio/webm" }), true, "s1");
    const [, options] = fetch.mock.calls[0];
    expect(options.body).toBeInstanceOf(FormData);
    expect(options.headers.has("Content-Type")).toBe(false);
  });
});
