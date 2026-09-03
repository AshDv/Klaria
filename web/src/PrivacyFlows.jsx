import { useEffect, useState } from "react";
import { api } from "./api";

export function PublicConsent({ token }) {
  const [notice, setNotice] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.getPublicConsent(token).then(setNotice).catch((requestError) => setError(requestError.message));
  }, [token]);

  async function act(action) {
    setError("");
    try {
      const response = await action(token);
      setMessage(response?.status === "accepted" ? "Votre consentement est enregistré." : "Votre consentement est retiré. L’enregistrement doit s’arrêter.");
      setNotice(await api.getPublicConsent(token));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  if (error && !notice) return <PublicShell><div className="alert error">{error}</div></PublicShell>;
  if (!notice) return <PublicShell><p>Chargement…</p></PublicShell>;
  const active = notice.consented_at && !notice.withdrawn_at;
  return <PublicShell>
    <span className="eyebrow">Consentement à l’enregistrement</span>
    <h1>{notice.meeting_title}</h1>
    <p>Bonjour {notice.participant_name}. Avant de choisir, voici exactement le traitement prévu.</p>
    <ul className="notice-list">
      <li>Votre voix et vos propos seront enregistrés.</li>
      <li>L’audio sera transmis à {notice.processor} pour transcription et diarisation.</li>
      <li>La transcription sera analysée pour produire le résumé, les décisions et les actions.</li>
      <li>{notice.media_recording_enabled ? `Vous acceptez aussi la conservation du replay audio pendant ${notice.media_retention_days} jour${notice.media_retention_days > 1 ? "s" : ""} maximum.` : "L’audio sera supprimé après le traitement."}</li>
      <li>Klaria ne capture, ne récupère et n’affiche ni la vidéo ni le partage d’écran.</li>
      <li>Les résultats seront conservés au maximum {notice.retention_days} jours.</li>
      <li>Vous pouvez retirer votre accord ou demander l’effacement depuis cette page.</li>
    </ul>
    <p className="privacy-hint">Contact : {notice.privacy_contact}</p>
    {notice.report_url && <a className="primary-button compact" href={notice.report_url}>Ouvrir mon compte rendu</a>}
    {message && <div className="alert success">{message}</div>}
    <div className="control-row">
      {!active && <button className="primary-button compact" onClick={() => act(api.acceptConsent)}>{notice.media_recording_enabled ? "J’accepte la transcription et le replay audio" : "J’accepte la transcription"}</button>}
      {!active && !notice.withdrawn_at && <button className="stop-button" onClick={() => act(api.withdrawConsent)}>Je refuse</button>}
      {active && <button className="stop-button" onClick={() => act(api.withdrawConsent)}>Retirer mon consentement</button>}
      <button className="secondary-button" onClick={async () => {
        if (!confirm("Effacer les données liées à cette réunion ?")) return;
        await api.eraseConsentData(token);
        setMessage("Les données liées à cette réunion ont été effacées.");
      }}>Demander l’effacement</button>
    </div>
  </PublicShell>;
}

export function PublicShell({ children }) {
  return <main className="public-page"><section className="content-card public-card"><div className="brand"><span className="brand-mark">K</span><span>Klaria</span></div>{children}</section></main>;
}

export function PublicReport({ token }) {
  const [meeting, setMeeting] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.getPublicReport(token).then(setMeeting).catch((requestError) => setError(requestError.message));
  }, [token]);

  async function erase() {
    if (!confirm("Retirer votre accord et effacer vos données de cette réunion ?")) return;
    try {
      await api.erasePublicReportData(token);
      setMeeting(null);
      setMessage("Votre demande est enregistrée. Vos passages sont supprimés et le compte rendu est régénéré sans vos données quand c’est possible.");
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  if (error && !meeting) return <PublicShell><div className="alert error">{error}</div></PublicShell>;
  if (message && !meeting) return <PublicShell><div className="alert success">{message}</div></PublicShell>;
  if (!meeting) return <PublicShell><p>Chargement du compte rendu…</p></PublicShell>;
  const report = meeting.report || {};
  return <PublicShell>
    <span className="eyebrow">Compte rendu partagé</span>
    <h1>{meeting.title}</h1>
    <p>Bonjour {meeting.viewer?.name}. Ce lien est personnel et reste contrôlé par votre consentement.</p>
    <section className="public-report-section">
      <h2>En bref</h2>
      <RichText value={report.executive_summary || "Compte rendu disponible."}/>
    </section>
    <section className="public-report-section">
      <h2>Actions</h2>
      {report.actions?.length ? <ul className="notice-list">{report.actions.map((item, index) => <li key={index}>{item.task}{item.owner ? ` — ${item.owner}` : ""}{item.due_date ? ` · ${item.due_date}` : ""}</li>)}</ul> : <p>Aucune action identifiée.</p>}
    </section>
    <section className="public-report-section">
      <h2>Compte rendu détaillé</h2>
      <RichText value={report.detailed_minutes || ""}/>
    </section>
    <section className="public-report-section">
      <h2>Transcription</h2>
      {meeting.segments?.length ? meeting.segments.map((segment) => <p key={segment.id}><strong>{segment.speaker}</strong> — {segment.text}</p>) : <p>Aucune transcription disponible.</p>}
    </section>
    {message && <div className="alert success">{message}</div>}
    {error && <div className="alert error">{error}</div>}
    <button className="stop-button" onClick={erase}>Retirer mon accord et effacer mes données</button>
  </PublicShell>;
}

function RichText({ value = "" }) {
  const blocks = value.replace(/\*\*/g, "").split(/\n{2,}/).map((item) => item.trim()).filter(Boolean);
  return <div className="rich-report">{blocks.map((block, index) => {
    const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
    if (lines.every((line) => /^[•*-]\s+/.test(line))) {
      return <ul key={index}>{lines.map((line, itemIndex) => <li key={itemIndex}>{line.replace(/^[•*-]\s+/, "")}</li>)}</ul>;
    }
    return <p key={index}>{lines.join(" ")}</p>;
  })}</div>;
}

export function PublicLegal({ type }) {
  const [notice, setNotice] = useState(null);
  useEffect(() => { api.legalNotices().then(setNotice); }, []);
  if (!notice) return <PublicShell><p>Chargement…</p></PublicShell>;
  if (type === "terms") return <PublicShell>
    <span className="eyebrow">Conditions d’utilisation · {notice.terms_version}</span>
    <h1>Utiliser Klaria de façon responsable</h1>
    <p>Klaria aide l’organisateur à transcrire et résumer une réunion. Il reste responsable de la réunion, de l’exactitude des informations fournies et du respect des droits des participants.</p>
    <ul className="notice-list"><li>Aucune capture ne doit commencer avant les consentements requis.</li><li>Le compte rendu généré par l’IA doit être relu avant toute décision.</li><li>Les accès au compte et aux agendas ne doivent pas être partagés.</li><li>Un participant peut retirer son accord et demander l’effacement.</li></ul>
    <p>Contact : <a href={`mailto:${notice.privacy_contact}`}>{notice.privacy_contact}</a></p>
  </PublicShell>;
  return <PublicShell>
    <span className="eyebrow">Politique de confidentialité · {notice.privacy_version}</span>
    <h1>Vos données, clairement</h1>
    <p><strong>Responsable du traitement :</strong> {notice.controller}, {notice.controller_address}</p>
    <h3>Données et traitements</h3><ul className="notice-list">{notice.processing.map((item) => <li key={item}>{item}</li>)}</ul>
    <h3>Finalités</h3><ul className="notice-list">{notice.purposes.map((item) => <li key={item}>{item}</li>)}</ul>
    <h3>Bases légales</h3><ul className="notice-list">{notice.legal_bases.map((item) => <li key={item}>{item}</li>)}</ul>
    <h3>Destinataires</h3><ul className="notice-list">{notice.recipients.map((item) => <li key={item}>{item}</li>)}</ul>
    <h3>Vos droits</h3><ul className="notice-list">{notice.rights.map((item) => <li key={item}>{item}</li>)}</ul>
    <p>Contact : <a href={`mailto:${notice.privacy_contact}`}>{notice.privacy_contact}</a></p>
  </PublicShell>;
}

export function LegalGate({ onAccepted }) {
  const [notice, setNotice] = useState(null);
  const [termsChecked, setTermsChecked] = useState(false);
  const [privacyChecked, setPrivacyChecked] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.legalNotices().then(setNotice).catch((requestError) => setError(requestError.message));
  }, []);

  async function accept() {
    try {
      await api.acceptLegal();
      onAccepted();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  return <PublicShell>
    <span className="eyebrow">Information obligatoire</span>
    <h1>Vos données, clairement</h1>
    {notice && <>
      <p><strong>Responsable du traitement :</strong> {notice.controller}, {notice.controller_address}</p>
      <h3>Traitements</h3><ul className="notice-list">{notice.processing.map((item) => <li key={item}>{item}</li>)}</ul>
      <h3>Pourquoi</h3><ul className="notice-list">{notice.purposes.map((item) => <li key={item}>{item}</li>)}</ul>
      <h3>Bases légales</h3><ul className="notice-list">{notice.legal_bases.map((item) => <li key={item}>{item}</li>)}</ul>
      <h3>Vos droits</h3><ul className="notice-list">{notice.rights.map((item) => <li key={item}>{item}</li>)}</ul>
      <p><strong>Sous-traitant :</strong> {notice.processors.join(", ")}</p>
      <p><strong>DPA :</strong> {notice.dpa_status}</p>
      <label className="consent"><input type="checkbox" checked={termsChecked} onChange={(event) => setTermsChecked(event.target.checked)} /><span><strong>J’accepte les CGU</strong><small>Version {notice.terms_version}</small></span></label>
      <label className="consent"><input type="checkbox" checked={privacyChecked} onChange={(event) => setPrivacyChecked(event.target.checked)} /><span><strong>Je reconnais avoir lu l’information RGPD</strong><small>Version {notice.privacy_version}</small></span></label>
    </>}
    {error && <div className="alert error">{error}</div>}
    <button className="primary-button compact" disabled={!termsChecked || !privacyChecked} onClick={accept}>Continuer</button>
  </PublicShell>;
}
