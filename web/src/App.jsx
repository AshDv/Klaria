import { useEffect, useState } from "react";
import { api, isAuthenticated, setAccessToken } from "./api";
import { MeetingWorkflow } from "./MeetingWorkflow";
import { LegalGate, PublicConsent } from "./PrivacyFlows";

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
  };
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
};

function consumeSsoToken() {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const token = params.get("access_token");
  if (token) {
    setAccessToken(token);
    history.replaceState(null, "", window.location.pathname);
  }
}

export default function App() {
  const match = window.location.pathname.match(/^\/consent\/([^/]+)$/);
  if (match) return <PublicConsent token={match[1]} />;
  return <AuthenticatedApp />;
}

function AuthenticatedApp() {
  consumeSsoToken();
  const [authenticated, setAuthenticated] = useState(isAuthenticated());
  const [user, setUser] = useState(null);
  const [view, setView] = useState("record");
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    if (!authenticated) return;
    api.me().then(setUser).catch(() => { setAccessToken(null); setAuthenticated(false); });
  }, [authenticated]);

  if (!authenticated) return <AuthScreen onAuthenticated={() => setAuthenticated(true)} />;
  if (!user) return <Loading />;
  if (!user.agreements_current) {
    return <LegalGate onAccepted={() => api.me().then(setUser)} />;
  }
  const openRecording = (id) => { setSelectedId(id); setView("result"); };
  const logout = () => { setAccessToken(null); setUser(null); setAuthenticated(false); };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <nav className="nav-list" aria-label="Navigation principale">
          <NavButton active={view === "record"} icon="mic" label="Nouveau résumé" onClick={() => setView("record")} />
          <NavButton active={view === "library" || view === "result"} icon="file" label="Mes enregistrements" onClick={() => setView("library")} />
          <NavButton active={view === "privacy"} icon="shield" label="Confidentialité" onClick={() => setView("privacy")} />
        </nav>
        <div className="profile-card">
          <div className="avatar">{(user?.full_name || user?.email || "S").slice(0, 1).toUpperCase()}</div>
          <div className="profile-copy"><strong>{user?.full_name || "Utilisateur"}</strong><span>{user?.email}</span></div>
          <button className="icon-button" onClick={logout} aria-label="Se déconnecter"><Icon name="logout" size={18} /></button>
        </div>
      </aside>

      <main className="main-content">
        {view === "record" && <MeetingWorkflow onCreated={openRecording} />}
        {view === "library" && <Library onOpen={openRecording} />}
        {view === "result" && <Result id={selectedId} onBack={() => setView("library")} />}
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
          <h1>Parlez.<br />Scribe organise.</h1>
          <p>Enregistrez votre échange et obtenez une transcription fidèle, un résumé et les prochaines actions.</p>
          <div className="feature-row"><span><Icon name="check" size={16} /> Audio protégé</span><span><Icon name="check" size={16} /> IA Mistral</span></div>
        </div>
        <small>Vos données restent sous votre contrôle.</small>
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <span className="eyebrow">Bienvenue sur Scribe</span>
          <h2>{mode === "login" ? "Ravi de vous revoir" : "Créer votre espace"}</h2>
          <p className="muted">Une minute suffit pour commencer.</p>
          <a className="google-button" href="/api/auth/sso/google"><GoogleLogo /> Continuer avec Google</a>
          <div className="separator"><span>ou avec votre e-mail</span></div>
          <form onSubmit={submit} className="auth-form">
            {mode === "register" && <Field label="Nom complet"><input value={fullName} onChange={e => setFullName(e.target.value)} minLength="2" required autoComplete="name" /></Field>}
            <Field label="Adresse e-mail"><input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="email" /></Field>
            <Field label="Mot de passe"><input type="password" value={password} onChange={e => setPassword(e.target.value)} minLength="10" required autoComplete={mode === "login" ? "current-password" : "new-password"} /><small>10 caractères minimum</small></Field>
            {mode === "register" && <>
              <label className="legal-check"><input type="checkbox" checked={privacyAccepted} onChange={(event) => setPrivacyAccepted(event.target.checked)} required /><span>J’ai lu l’information RGPD : compte, consentements, audio envoyé à Mistral, conservation limitée et droits d’effacement.</span></label>
              <label className="legal-check"><input type="checkbox" checked={termsAccepted} onChange={(event) => setTermsAccepted(event.target.checked)} required /><span>J’accepte séparément les conditions générales d’utilisation de Scribe.</span></label>
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

function Field({ label, children }) { return <label className="field"><span>{label}</span>{children}</label>; }

function Library({ onOpen }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api.listRecordings().then(setItems).catch(err => setError(err.message)); }, []);
  return <section className="page"><header className="page-header"><div><span className="eyebrow">Votre espace</span><h1>Mes enregistrements</h1><p>Retrouvez vos transcriptions et vos résumés.</p></div></header>{error && <div className="alert error">{error}</div>}{items === null ? <Loading /> : items.length === 0 ? <div className="empty-card"><Icon name="file" size={30}/><h3>Aucun enregistrement</h3><p>Votre premier compte rendu apparaîtra ici.</p></div> : <div className="recording-list">{items.map(item => <button key={item.id} className="recording-row" onClick={() => onOpen(item.id)}><span className="file-icon"><Icon name="file" /></span><span className="recording-copy"><strong>{item.title}</strong><small>{new Date(item.created_at).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" })}</small></span><Status status={item.status}/><span className="arrow">→</span></button>)}</div>}</section>;
}

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
    <ResultList title="Décisions" items={report.decisions.map((item) => `${item.decision}${item.decided_by.length ? ` — ${item.decided_by.map(speakerName).join(", ")}` : ""}`)} />
    <ResultList title="Actions" items={report.actions.map((item) => `${item.task}${item.owner ? ` — ${speakerName(item.owner)}` : " — responsable non précisé"}${item.due_date ? ` — ${item.due_date}` : ""}`)} />
    <ResultList title="Questions ouvertes" items={report.open_questions.map((item) => item.question)} />
    <ResultList title="Risques" items={report.risks.map((item) => item.risk)} />
    <article className="content-card"><span className="card-label">Intervenants</span><ul>{report.speakers.map((speaker) => <li key={speaker.label}><span><Icon name="check" size={15}/></span>{speaker.label} — {speaker.participant_name || "identité non confirmée"}</li>)}</ul></article>
    <p className="coverage-note">{report.coverage.length}/{segments.length} segments analysés et tracés.</p>
  </>;
}
function Status({ status }) { const labels = { uploaded: "Envoyé", processing: "Traitement", completed: "Terminé", failed: "Échec" }; return <span className={`status ${status}`}>{labels[status] || status}</span>; }
function Loading() { return <div className="loading"><span className="large-spinner"/><p>Chargement…</p></div>; }

function Privacy() {
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

  return <section className="page"><header className="page-header"><div><span className="eyebrow">Vos droits</span><h1>Confidentialité</h1><p>Collecter le strict nécessaire, expliquer clairement et supprimer réellement.</p></div></header><div className="privacy-grid"><article className="content-card"><h3>Finalité et base légale</h3><p>Le consentement autorise uniquement l’enregistrement, la transcription diarisée et la production du compte rendu demandé.</p></article><article className="content-card"><h3>Sous-traitant IA</h3><p>L’audio et la transcription sont envoyés à Mistral AI. Aucun e-mail de participant n’est transmis au modèle.</p></article><article className="content-card"><h3>Conservation</h3><p>L’audio est supprimé après le traitement. Les résultats sont conservés au maximum 30 jours.</p></article><article className="content-card"><h3>Retrait</h3><p>Chaque participant peut retirer son accord depuis son e-mail. Le dictaphone s’arrête automatiquement.</p></article></div><div className="privacy-actions"><button className="secondary-button" onClick={exportData}>Exporter mes données</button><button className="stop-button" onClick={deleteAccount}>Supprimer mon compte</button></div></section>;
}
