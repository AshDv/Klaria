import { useEffect, useState } from "react";
import { api } from "./api";

export function PublicConsent() { return null; }

export function LegalGate({ onAccepted }) {
  const [notice, setNotice] = useState(null);
  const [accepted, setAccepted] = useState(false);
  useEffect(() => { api.legalNotices().then(setNotice); }, []);
  async function accept() { await api.acceptLegal(); onAccepted(); }
  if (!notice) return <main className="public-page">Chargement…</main>;
  return <main className="public-page"><section className="content-card public-card">
    <h1>Vos données, clairement</h1>
    <p>{notice.processing.join(" ")}</p>
    <label className="legal-check"><input type="checkbox" onChange={event => setAccepted(event.target.checked)} /> J’accepte les CGU et reconnais avoir lu l’information RGPD.</label>
    <button className="primary-button" disabled={!accepted} onClick={accept}>Continuer</button>
  </section></main>;
}
