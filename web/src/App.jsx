import { useEffect, useState } from "react";
import { api, isAuthenticated, setAccessToken } from "./api";
import { ActionsView, Dashboard } from "./Dashboard";
import { MeetingsHub } from "./CalendarAutomation";
import { PodcastPlayer } from "./PodcastPlayer";
import { LegalGate, PublicConsent, PublicLegal } from "./PrivacyFlows";
import { NewMeeting } from "./RemoteMeetingWorkflow";
import { RemoteMeetingView } from "./RemoteMeetingView";

const Icon = ({ name, size = 20 }) => {
  const paths = {
    mic: <><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3"/></>,
    home: <><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10M9 20v-6h6v6"/></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16h16V8Z"/><path d="M14 2v6h6M8 13h8M8 17h6"/></>,
    shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></>,
    logout: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M21 19V5a2 2 0 0 0-2-2h-6"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    trash: <><path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6M10 11v6M14 11v6"/></>,
    rotate: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></>,
    bot: <><rect x="4" y="6" width="16" height="13" rx="4"/><path d="M12 2v4M8 11h.01M16 11h.01M8 15h8"/></>,
    tasks: <><path d="M9 6h11M9 12h11M9 18h11"/><path d="m3 6 1 1 2-2M3 12l1 1 2-2M3 18l1 1 2-2"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18M8 14h.01M12 14h.01M16 14h.01"/></>,
  };
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
};

function consumeSsoToken() {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const token = params.get("access_token");
  if (token) {
    setAccessToken(token);
    history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  }
}

export default function App() {
  const match = window.location.pathname.match(/^\/consent\/([^/]+)$/);
  if (match) return <PublicConsent token={match[1]} />;
  if (window.location.pathname === "/privacy-policy") return <PublicLegal type="privacy" />;
  if (window.location.pathname === "/terms") return <PublicLegal type="terms" />;
  return <AuthenticatedApp />;
}

function AuthenticatedApp() {
  consumeSsoToken();
  const deepLink = window.location.pathname.match(/^\/meeting\/([^/]+)$/);
  const params = new URLSearchParams(window.location.search);
  const teamsMode = params.get("host") === "teams";
  const requestedView = params.get("view");
  const initialView = ["dashboard", "meetings", "actions", "privacy"].includes(requestedView)
    ? requestedView
    : "dashboard";
  const [authenticated, setAuthenticated] = useState(isAuthenticated());
  const [user, setUser] = useState(null);
  const [view, setView] = useState(deepLink ? "remote" : initialView);
  const [selectedId, setSelectedId] = useState(deepLink?.[1] || null);

  useEffect(() => {
    if (!teamsMode) return undefined;
    let active = true;
    import("@microsoft/teams-js").then(async ({ app }) => {
      await app.initialize();
      const context = await app.getContext();
      if (!active) return;
      document.documentElement.dataset.teamsTheme = context.app.theme || "default";
      app.registerOnThemeChangeHandler((theme) => {
        document.documentElement.dataset.teamsTheme = theme;
      });
    }).catch(() => {});
    return () => { active = false; };
  }, [teamsMode]);

  useEffect(() => {
    if (!authenticated) return;
    api.me().then(setUser).catch(() => { setAccessToken(null); setAuthenticated(false); });
  }, [authenticated]);

  if (!authenticated) return <AuthScreen onAuthenticated={() => setAuthenticated(true)} />;
  if (!user) return <Loading />;
  if (!user.agreements_current) {
    return <LegalGate onAccepted={() => api.me().then(setUser)} />;
  }
  const goTo = (nextView) => {
    setView(nextView);
    history.replaceState(null, "", teamsMode ? `/?host=teams&view=${nextView}` : "/");
  };
  const openRecording = (id) => { setSelectedId(id); setView("result"); };
  const openRemote = (id) => {
    setSelectedId(id);
    setView("remote");
    history.replaceState(null, "", `/meeting/${id}${teamsMode ? "?host=teams" : ""}`);
  };
  const openItem = (item) => item.source === "bot" ? openRemote(item.id) : openRecording(item.id);
  const logout = () => { setAccessToken(null); setUser(null); setAuthenticated(false); };

  return (
    <div className={`app-shell ${teamsMode ? "teams-shell" : ""}`}>
      <aside className="sidebar">
        <Brand />
        <nav className="nav-list" aria-label="Navigation principale">
          <NavButton active={view === "dashboard"} icon="home" label="Accueil" onClick={() => goTo("dashboard")} />
          <NavButton active={["meetings", "new", "result", "remote"].includes(view)} icon="calendar" label="Réunions" onClick={() => goTo("meetings")} />
          <NavButton active={view === "actions"} icon="tasks" label="Actions" onClick={() => goTo("actions")} />
          <NavButton active={view === "privacy"} icon="shield" label="Confidentialité" onClick={() => goTo("privacy")} />
        </nav>
        <div className="profile-card">
          <div className="avatar">{(user?.full_name || user?.email || "S").slice(0, 1).toUpperCase()}</div>
          <div className="profile-copy"><strong>{user?.full_name || "Utilisateur"}</strong><span>{user?.email}</span></div>
          <button className="icon-button" onClick={logout} aria-label="Se déconnecter"><Icon name="logout" size={18} /></button>
        </div>
      </aside>

      <main className="main-content">
        {view === "dashboard" && <Dashboard user={user} onNewBot={() => goTo("new")} onOpen={openItem} />}
        {view === "new" && <NewMeeting user={user} onRemoteCreated={openRemote} onRecordingCreated={openRecording} />}
        {view === "meetings" && <MeetingsHub onNew={() => goTo("new")} onOpenRecording={openRecording} onOpenRemote={openRemote} />}
        {view === "result" && <Result id={selectedId} onBack={() => goTo("meetings")} />}
        {view === "remote" && <RemoteMeetingView id={selectedId} onBack={() => goTo("meetings")} />}
        {view === "actions" && <ActionsView />}
        {view === "privacy" && <Privacy />}
      </main>
    </div>
  );
}

function Brand() {
  return <div className="brand"><span className="brand-mark"><Icon name="mic" size={21} /></span><span>Scribe</span></div>;
}

function NavButton({ active, icon, label, onClick }) {
  return <button className={`nav-button ${active ? "active" : ""}`} onClick={onClick}><Icon name={icon} size={19} />{label}</button>;
}

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if (mode === "register") {
        await api.register(
          fullName,
          email,
          password,
          termsAccepted,
          privacyAccepted,
        );
      } else await api.login(email, password);
      onAuthenticated();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  return (
    <div className="auth-layout">
      <section className="auth-story">
        <Brand />
        <div className="story-copy">
          <span className="eyebrow">La réunion devient claire</span>
          <h1>Votre réunion.<br />Enfin exploitable.</h1>
          <p>Scribe rejoint Meet ou Teams, distingue les voix et transforme le direct en décisions, actions et compte rendu.</p>
          <div className="feature-row"><span><Icon name="check" size={16} /> Meet + Teams</span><span><Icon name="check" size={16} /> IA Mistral</span></div>
        </div>
        <small>Vos données restent sous votre contrôle.</small>
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <span className="eyebrow">Bienvenue sur Scribe</span>
          <h2>{mode === "login" ? "Ravi de vous revoir" : "Créer votre espace"}</h2>
          <p className="muted">Une minute suffit pour commencer.</p>
          <a className="google-button" href={api.googleSsoUrl()}><GoogleLogo /> Continuer avec Google</a>
          <a className="microsoft-button" href={api.microsoftSsoUrl()}><MicrosoftLogo /> Continuer avec Microsoft</a>
          <div className="separator"><span>ou avec votre e-mail</span></div>
          <form onSubmit={submit} className="auth-form">
            {mode === "register" && <Field label="Nom complet"><input value={fullName} onChange={e => setFullName(e.target.value)} minLength="2" required autoComplete="name" /></Field>}
            <Field label="Adresse e-mail"><input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="email" /></Field>
            <Field label="Mot de passe"><input type="password" value={password} onChange={e => setPassword(e.target.value)} minLength="10" required autoComplete={mode === "login" ? "current-password" : "new-password"} /><small>10 caractères minimum</small></Field>
            {mode === "register" && <>
              <label className="legal-check"><input type="checkbox" checked={privacyAccepted} onChange={(event) => setPrivacyAccepted(event.target.checked)} required /><span>J’ai lu la <a href="/privacy-policy" target="_blank">politique de confidentialité</a> : traitements, conservation et droits d’effacement.</span></label>
              <label className="legal-check"><input type="checkbox" checked={termsAccepted} onChange={(event) => setTermsAccepted(event.target.checked)} required /><span>J’accepte séparément les <a href="/terms" target="_blank">conditions d’utilisation</a> de Scribe.</span></label>
            </>}
            {error && <div className="alert error">{error}</div>}
            <button className="primary-button" disabled={busy}>{busy ? "Veuillez patienter…" : mode === "login" ? "Se connecter" : "Créer mon compte"}</button>
          </form>
          <button className="text-button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
            {mode === "login" ? "Pas encore de compte ? S’inscrire" : "Déjà inscrit ? Se connecter"}
          </button>
        </div>
      </section>
    </div>
  );
}

function GoogleLogo() {
  return <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1Z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.16v2.84A11 11 0 0 0 12 23Z"/><path fill="#FBBC05" d="M5.84 14.09A6.6 6.6 0 0 1 5.5 12c0-.73.13-1.43.34-2.09V7.07H2.16A11 11 0 0 0 1 12c0 1.77.42 3.45 1.16 4.93l3.68-2.84Z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.2 1.64l3.15-3.15A10.6 10.6 0 0 0 12 1 11 11 0 0 0 2.16 7.07l3.68 2.84C6.71 7.31 9.14 5.38 12 5.38Z"/></svg>;
}

function MicrosoftLogo() {
  return <span className="microsoft-logo" aria-hidden="true"><i/><i/><i/><i/></span>;
}

function Field({ label, children }) { return <label className="field"><span>{label}</span>{children}</label>; }

function Result({ id, onBack }) {
  const [item, setItem] = useState(null); const [error, setError] = useState("");
  async function load() { try { setItem(await api.getRecording(id)); } catch (err) { setError(err.message); } }
  useEffect(() => {
    load();
    if (item?.status === "completed" || item?.status === "failed") return undefined;
    const timer = setInterval(load, 2500);
    return () => clearInterval(timer);
  }, [id, item?.status]);
  async function remove() { if (!confirm("Supprimer définitivement cet enregistrement et ses résultats ?")) return; await api.deleteRecording(id); onBack(); }
  if (error) return <div className="alert error">{error}</div>;
  if (!item) return <Loading />;
  const waiting = item.status === "uploaded" || item.status === "processing";
  return <section className="page"><button className="back-button" onClick={onBack}>← Mes enregistrements</button><header className="result-header"><div><Status status={item.status}/><h1>{item.title}</h1><p>{new Date(item.created_at).toLocaleString("fr-FR", { dateStyle: "long", timeStyle: "short" })}</p></div><button className="icon-button danger" onClick={remove} aria-label="Supprimer"><Icon name="trash"/></button></header>{waiting && <div className="processing-card"><span className="large-spinner"/><h2>Scribe prépare votre compte rendu</h2><p>Voxtral sépare les intervenants, puis Mistral Medium 3.5 organise les informations.</p></div>}{item.status === "failed" && <div className="processing-card error-state"><h2>Le traitement n’a pas abouti</h2><p>{item.error}</p><p>L’audio a été supprimé par sécurité. Effectuez un nouvel enregistrement.</p></div>}{item.status === "completed" && <div className="result-grid"><article className="content-card summary-card"><span className="card-label">Résumé exécutif</span><p className="summary-text">{item.summary}</p></article>{item.report ? <DetailedReport report={item.report} segments={item.segments} /> : <><ResultList title="Décisions" items={item.decisions}/><ResultList title="Actions" items={item.actions.map(action => `${action.task}${action.owner ? ` — ${action.owner}` : ""}`)}/></>}<article className="content-card transcript-card"><span className="card-label">Transcription diarisée</span>{item.segments.length ? item.segments.map((segment) => <p key={segment.id}><strong>{segment.speaker}</strong> [{segment.start}s] — {segment.text}</p>) : <p>{item.transcript}</p>}</article></div>}</section>;
}

function ResultList({ title, items }) { return <article className="content-card"><span className="card-label">{title}</span>{items.length ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}><span><Icon name="check" size={15}/></span>{item}</li>)}</ul> : <p className="muted">Aucun élément identifié.</p>}</article>; }
function DetailedReport({ report, segments }) {
  const speakerName = (label) => report.speakers.find((item) => item.label === label)?.participant_name || label;
  return <>
    <article className="content-card summary-card"><span className="card-label">Compte rendu détaillé</span><p className="summary-text">{report.detailed_minutes}</p></article>
    <PodcastPlayer script={report.podcast_script || []} />
    <ResultList title="Décisions" items={report.decisions.map((item) => `${item.decision}${item.decided_by.length ? ` — ${item.decided_by.map(speakerName).join(", ")}` : ""}`)} />
    <ResultList title="Actions" items={report.actions.map((item) => `${item.task}${item.owner ? ` — ${speakerName(item.owner)}` : " — responsable non précisé"}${item.due_date ? ` — ${item.due_date}` : ""}`)} />
    <ResultList title="Questions ouvertes" items={report.open_questions.map((item) => item.question)} />
    <ResultList title="Risques" items={report.risks.map((item) => item.risk)} />
    <article className="content-card"><span className="card-label">Intervenants</span><ul>{report.speakers.map((speaker) => <li key={speaker.label}><span><Icon name="check" size={15}/></span>{speaker.label} — {speaker.participant_name || "identité non confirmée"}</li>)}</ul></article>
    <p className="coverage-note">{report.coverage.length}/{segments.length} segments analysés et tracés.</p>
  </>;
}
function Status({ status }) { const labels = { uploaded: "Envoyé", processing: "Traitement", joining: "Connexion", live: "En direct", finalizing: "Analyse", completed: "Terminé", stopped: "Arrêté", failed: "Échec" }; return <span className={`status ${status}`}>{labels[status] || status}</span>; }
function Loading() { return <div className="loading"><span className="large-spinner"/><p>Chargement…</p></div>; }

function Privacy() {
  const [notice, setNotice] = useState(null);
  useEffect(() => { api.legalNotices().then(setNotice); }, []);

  async function exportData() {
    const data = await api.exportData();
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "scribe-mes-donnees.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  async function deleteAccount() {
    if (!confirm("Supprimer définitivement votre compte et toutes ses données ?")) return;
    await api.deleteAccount();
    setAccessToken(null);
    window.location.reload();
  }

  const retention = notice?.retention_days;
  return <section className="page"><header className="page-header"><div><span className="eyebrow">Vos droits</span><h1>Confidentialité</h1><p>Collecter le strict nécessaire, expliquer clairement et supprimer réellement.</p></div></header><div className="privacy-grid"><article className="content-card"><h3>Finalité et base légale</h3><p>Le consentement autorise uniquement la capture, la transcription diarisée et la production du compte rendu demandé.</p></article><article className="content-card"><h3>Sous-traitants</h3><p>Vexa transcrit les réunions en ligne et Mistral produit le compte rendu. Aucun e-mail n’est transmis aux modèles.</p></article><article className="content-card"><h3>Conservation</h3><p>Le bot ne conserve pas l’audio ni le chat et ses données temporaires sont purgées après l’analyse. Les résultats expirent après {retention || "…"} jours.</p></article><article className="content-card"><h3>Retrait</h3><p>Chaque participant peut utiliser son lien ou écrire STOP SCRIBE dans le chat. Le bot s’arrête et efface alors le direct.</p></article></div><div className="privacy-actions"><button className="secondary-button" onClick={exportData}>Exporter mes données</button><button className="stop-button" onClick={deleteAccount}>Supprimer mon compte</button></div></section>;
}
