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
      <li>Nolya ne capture, ne récupère et n’affiche ni la vidéo ni le partage d’écran.</li>
      <li>Les résultats seront conservés au maximum {notice.retention_days} jours.</li>
      <li>Vous pouvez retirer votre accord ou demander l’effacement depuis cette page.</li>
    </ul>
    <p className="privacy-hint">Contact : {notice.privacy_contact}</p>
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
  return <main className="public-page"><section className="content-card public-card"><div className="brand"><span className="brand-mark">N</span><span>Nolya</span></div>{children}</section></main>;
}

export function PublicLegal({ type }) {
  const [notice, setNotice] = useState(null);
  useEffect(() => { api.legalNotices().then(setNotice); }, []);
  if (!notice) return <PublicShell><p>Chargement…</p></PublicShell>;
  if (type === "terms") return <PublicShell>
    <span className="eyebrow">Conditions d’utilisation · {notice.terms_version}</span>
    <h1>Utiliser Nolya de façon responsable</h1>
    <p>Nolya aide l’organisateur à transcrire et résumer une réunion. Il reste responsable de la réunion, de l’exactitude des informations fournies et du respect des droits des participants.</p>
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
