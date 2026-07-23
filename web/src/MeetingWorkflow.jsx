import { useState } from "react";
import { api } from "./api";

export function MeetingWorkflow({ onCreated }) {
  const [title, setTitle] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  async function submit(event) {
    event.preventDefault();
    const meeting = await api.createConsentSession({
      title,
      participants: [{ name, email }],
    });
    onCreated(meeting);
  }
  return <section className="page"><h1>Préparer une réunion</h1><form className="meeting-form content-card" onSubmit={submit}>
    <input value={title} onChange={event => setTitle(event.target.value)} placeholder="Titre" required />
    <input value={name} onChange={event => setName(event.target.value)} placeholder="Participant" required />
    <input type="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="E-mail" required />
    <button className="primary-button">Envoyer la demande de consentement</button>
  </form></section>;
}
