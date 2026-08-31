import { useEffect, useState } from "react";

import { api } from "./api";
import { instant, parisDateTime } from "./dateTime";
import { MeetingWorkflow } from "./MeetingWorkflow";
import { PlatformIcon } from "./PlatformIcon";

export function NewMeeting({ onRemoteCreated, onRecordingCreated }) {
  const [mode, setMode] = useState("bot");
  return <section className="page">
    <header className="page-header new-meeting-header"><div><span className="eyebrow">Nouvelle réunion</span><h1>Comment échangez-vous ?</h1><p>Choisissez le mode adapté, le résultat reste le même : clair et exploitable.</p></div></header>
    <div className="mode-switch" role="tablist">
      <button className={mode === "bot" ? "active" : ""} onClick={() => setMode("bot")}><span className="mode-icon">S</span><strong>Meet ou Teams</strong><small>Klaria rejoint la réunion</small></button>
      <button className={mode === "room" ? "active" : ""} onClick={() => setMode("room")}><span className="mode-icon room">●</span><strong>En présentiel</strong><small>Utiliser le dictaphone</small></button>
    </div>
    {mode === "bot" ? <BotFlow onCreated={onRemoteCreated}/> : <MeetingWorkflow onCreated={onRecordingCreated}/>}
  </section>;
}

function BotFlow({ onCreated }) {
  const [setup, setSetup] = useState(null);
  return setup ? <BotConsent setup={setup} onCreated={onCreated}/> : <BotSetup onCreated={setSetup}/>;
}

function BotSetup({ onCreated }) {
  const [title, setTitle] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [meetingUrl, setMeetingUrl] = useState("");
  const [teamsMeetingId, setTeamsMeetingId] = useState("");
  const [teamsPasscode, setTeamsPasscode] = useState("");
  const [participants, setParticipants] = useState([{ name: "", email: "" }]);
  const [keepReplay, setKeepReplay] = useState(false);
  const [replayDays, setReplayDays] = useState(7);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [calendarEvents, setCalendarEvents] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [manual, setManual] = useState(false);
  const [eventQuery, setEventQuery] = useState("");
  const isTeams = meetingUrl.includes("teams.");
  const needsTeamsDetails = isTeams && !/\/meet\/\d{8,15}/.test(meetingUrl);
  const matchingEvents = (calendarEvents || []).filter((item) => `${item.title} ${item.attendees.map((person) => person.name).join(" ")}`
    .toLocaleLowerCase("fr").includes(eventQuery.trim().toLocaleLowerCase("fr")));

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const status = await api.calendarStatus();
        if (status.connections.some((item) => item.active)) await api.syncCalendars();
        const events = (await api.calendarEvents()).filter(
          (item) => item.status === "scheduled" && instant(item.starts_at) > new Date(Date.now() - 3600000),
        );
        if (!active) return;
        setCalendarEvents(events);
        if (events.length === 1) chooseEvent(events[0]);
      } catch (err) {
        if (active) { setCalendarEvents([]); setError(err.message); }
      }
    })();
    return () => { active = false; };
  }, []);

  function chooseEvent(event) {
    if (!event) return;
    setSelectedEvent(event);
    setTitle(event.title);
    setScheduledAt(event.starts_at);
    setMeetingUrl(event.meeting_url);
    setParticipants(event.attendees);
    setError("");
  }

  const update = (index, field, value) => setParticipants((items) => items.map(
    (item, position) => position === index ? { ...item, [field]: value } : item,
  ));

  async function importInvitation(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const invitation = parseInvitation(await file.text());
      if (invitation.title) setTitle(invitation.title);
      if (invitation.meetingUrl) setMeetingUrl(invitation.meetingUrl);
      if (invitation.scheduledAt) setScheduledAt(invitation.scheduledAt);
      if (invitation.participants.length) setParticipants(invitation.participants);
      setSelectedEvent(null);
      setManual(true);
      setError(invitation.meetingUrl ? "" : "Le lien Meet ou Teams manque dans cette invitation.");
    } catch { setError("Cette invitation calendrier n'a pas pu être lue."); }
  }

  async function create(event) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if (selectedEvent) {
        const configured = await api.configureCalendarEvent(selectedEvent.id, true, {
          media_recording_enabled: keepReplay,
          media_retention_days: replayDays,
        });
        const consent = await api.getConsentSession(configured.consent_session_id);
        onCreated({ consent, meetingUrl: configured.meeting_url, language: "fr" });
        return;
      }
      let botUrl = meetingUrl.trim();
      if (needsTeamsDetails) {
        const meetingId = teamsMeetingId.replace(/\s/g, "");
        if (!/^\d{8,15}$/.test(meetingId) || !teamsPasscode.trim()) {
          throw new Error("Renseignez l’identifiant numérique et le code secret affichés dans l’invitation Teams.");
        }
        botUrl = `https://teams.live.com/meet/${meetingId}?p=${encodeURIComponent(teamsPasscode.trim())}`;
      }
      const consent = await api.createConsentSession({
        title,
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
        participants,
        media_recording_enabled: keepReplay,
        media_retention_days: replayDays,
        platform: meetingUrl.includes("meet.google.com") ? "google_meet" : "teams",
      });
      onCreated({ consent, meetingUrl: botUrl, language: "fr" });
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  return <div className="launch-grid">
    <form className="content-card bot-form" onSubmit={create}>
      <div className="form-intro"><span className="platform-pair"><i><PlatformIcon platform="google_meet" decorative/></i><i><PlatformIcon platform="teams" decorative/></i></span><div><h2>Inviter l’assistant</h2><p>Klaria apparaîtra comme un participant visible.</p></div></div>
      {!manual && !selectedEvent && <div className="calendar-picker">
        <label className="field"><span>Choisir une réunion détectée</span><input type="search" value={eventQuery} onChange={(event) => setEventQuery(event.target.value)} placeholder="Rechercher par titre ou participant"/></label>
        <div className="calendar-picker-list">{calendarEvents === null
          ? <p className="muted">Synchronisation…</p>
          : matchingEvents.length
            ? matchingEvents.slice(0, 6).map((item) => <button type="button" key={item.id} onClick={() => chooseEvent(item)}><span><strong>{item.title}</strong><small>{parisDateTime(item.starts_at)} · heure de Paris</small></span><em><PlatformIcon platform={item.platform} decorative/>{item.platform === "teams" ? "Teams" : "Meet"}</em></button>)
            : <p className="muted">Aucune réunion correspondante.</p>}</div>
        {matchingEvents.length > 6 && <small className="picker-hint">Affinez la recherche pour trouver l’une des {matchingEvents.length} réunions.</small>}
      </div>}
      {selectedEvent && !manual && <div className="calendar-metadata"><span className="card-label">Informations récupérées automatiquement</span><strong>{selectedEvent.title}</strong><p>{parisDateTime(selectedEvent.starts_at, "long")} · heure de Paris</p><div>{selectedEvent.attendees.map((person) => <span key={person.email}>{person.name}</span>)}</div><small>{selectedEvent.attendees.length} invité(s) recevront la demande de consentement.</small></div>}
      {selectedEvent && !manual && <button type="button" className="text-button inline" onClick={() => setSelectedEvent(null)}>Choisir une autre réunion</button>}
      <button type="button" className="text-button inline manual-toggle" onClick={() => { setManual(!manual); setSelectedEvent(null); }}>{manual ? "Revenir à l’agenda" : "Saisie manuelle de secours"}</button>
      {manual && <>
      <label className="calendar-drop"><input type="file" accept=".ics,text/calendar" onChange={importInvitation}/><strong>Importer une invitation calendrier</strong><span>Klaria lit automatiquement le lien, l’heure et les invités du fichier .ics.</span></label>
      <label className="field"><span>Lien Google Meet ou Microsoft Teams</span><input type="url" value={meetingUrl} onChange={(event) => setMeetingUrl(event.target.value)} placeholder="https://meet.google.com/abc-defg-hij" required/></label>
      {needsTeamsDetails && <div className="calendar-import">
        <label className="field"><span>Identifiant de réunion Teams</span><input inputMode="numeric" value={teamsMeetingId} onChange={(event) => setTeamsMeetingId(event.target.value)} placeholder="123 456 789 012" required/></label>
        <label className="field"><span>Code secret Teams</span><input value={teamsPasscode} onChange={(event) => setTeamsPasscode(event.target.value)} placeholder="AbC123" required/></label>
        <p className="privacy-hint">Ces deux valeurs figurent sous le lien dans l’invitation Teams.</p>
      </div>}
      <label className="field"><span>Nom de la réunion</span><input value={title} onChange={(event) => setTitle(event.target.value)} required/></label>
      <label className="field"><span>Date et heure prévues</span><input type="datetime-local" value={scheduledAt} onChange={(event) => setScheduledAt(event.target.value)}/></label>
      <div className="participant-heading"><h3>Personnes enregistrées</h3><button type="button" className="text-button inline" onClick={() => setParticipants([...participants, { name: "", email: "" }])}>＋ Ajouter</button></div>
      {participants.map((participant, index) => <div className="participant-fields" key={index}>
        <input aria-label={`Nom ${index + 1}`} placeholder="Nom complet" value={participant.name} onChange={(event) => update(index, "name", event.target.value)} required/>
        <input aria-label={`E-mail ${index + 1}`} type="email" placeholder="E-mail" value={participant.email} onChange={(event) => update(index, "email", event.target.value)} required/>
        {participants.length > 1 && <button type="button" className="icon-button danger" onClick={() => setParticipants(participants.filter((_, position) => position !== index))} aria-label="Retirer">×</button>}
      </div>)}
      </>}
      <label className="consent replay-consent"><input type="checkbox" checked={keepReplay} onChange={(event) => setKeepReplay(event.target.checked)}/><span><strong>Conserver un replay audio</strong><small>Optionnel et désactivé par défaut. Chaque participant verra cette durée avant d’accepter.</small></span></label>
      {keepReplay && <label className="field compact-field"><span>Suppression automatique du média</span><select value={replayDays} onChange={(event) => setReplayDays(Number(event.target.value))}><option value="1">Après 24 heures</option><option value="7">Après 7 jours</option><option value="14">Après 14 jours</option><option value="30">Après 30 jours</option></select></label>}
      <p className="privacy-hint">Chaque personne reçoit un lien individuel. Le bot reste bloqué jusqu’au dernier accord. Klaria ne capture ni la vidéo ni le partage d’écran.</p>
      {error && <div className="alert error">{error}</div>}
      <button className="primary-button compact" disabled={busy || (!manual && !selectedEvent)}>{busy ? "Préparation…" : "Demander les accords"}</button>
    </form>
    <aside className="launch-aside"><span className="card-label">Déroulé</span><Step number="01" title="Accords" text="Chacun confirme par e-mail."/><Step number="02" title="Admission" text="L’hôte accepte Klaria dans la réunion."/><Step number="03" title="Compte rendu" text="Le direct devient décisions et actions."/></aside>
  </div>;
}

function BotConsent({ setup, onCreated }) {
  const [meeting, setMeeting] = useState(setup.consent);
  const [notice, setNotice] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = setInterval(() => api.getConsentSession(meeting.id).then(setMeeting).catch(() => {}), 3000);
    return () => clearInterval(timer);
  }, [meeting.id]);

  async function inviteBot() {
    if (!notice) { setError("Confirmez que tous les participants voient que Klaria va rejoindre."); return; }
    setBusy(true); setError("");
    try {
      await api.startConsentSession(meeting.id);
      const remote = await api.createRemoteMeeting({
        consent_session_id: meeting.id,
        meeting_url: setup.meetingUrl,
        language: setup.language,
      });
      onCreated(remote.id);
    } catch (err) { setError(err.message); setBusy(false); }
  }

  return <div className="consent-stage">
    <div className="content-card consent-dashboard bot-consent-card">
      <div className="consent-title"><span className="eyebrow">Avant de rejoindre</span><h2>{meeting.title}</h2><p>{meeting.participants.filter((item) => item.consented_at && !item.withdrawn_at).length}/{meeting.participants.length} accords actifs</p></div>
      <div className="consent-progress"><span style={{ width: `${meeting.participants.filter((item) => item.consented_at && !item.withdrawn_at).length / meeting.participants.length * 100}%` }}/></div>
      {meeting.participants.map((participant) => <div className="consent-row" key={participant.id}><div><strong>{participant.name}</strong><small>{participant.email}</small></div><span className={`status ${participant.consented_at && !participant.withdrawn_at ? "completed" : "uploaded"}`}>{participant.withdrawn_at ? "Retiré" : participant.consented_at ? "Accepté" : "E-mail envoyé"}</span></div>)}
      <label className="consent"><input type="checkbox" checked={notice} onChange={(event) => setNotice(event.target.checked)}/><span><strong>La présence du bot sera visible et annoncée</strong><small>Chaque participant peut retirer son accord à tout moment.</small></span></label>
      <div className="consent-mode"><strong>{meeting.media_recording_enabled ? "Replay audio activé" : "Mode sans replay audio"}</strong><span>{meeting.media_recording_enabled ? `Suppression automatique après ${meeting.media_retention_days} jour${meeting.media_retention_days > 1 ? "s" : ""}.` : "Seul le texte utile sera conservé."}</span></div>
      {error && <div className="alert error">{error}</div>}
      <button className="primary-button compact" onClick={inviteBot} disabled={!meeting.all_consented || busy}>{busy ? "Connexion de Klaria…" : "Inviter Klaria maintenant"}</button>
    </div>
  </div>;
}

function Step({ number, title, text }) { return <div className="launch-step"><span>{number}</span><div><strong>{title}</strong><p>{text}</p></div></div>; }

function parseInvitation(raw) {
  const text = raw.replace(/\r?\n[ \t]/g, "");
  const lines = text.split(/\r?\n/);
  const value = (name) => lines.find((line) => line.startsWith(`${name}:`) || line.startsWith(`${name};`))?.split(":").slice(1).join(":");
  const content = [value("URL"), value("LOCATION"), value("DESCRIPTION")].filter(Boolean).join(" ").replace(/\\n/g, " ");
  const meetingUrl = content.match(/https:\/\/(?:meet\.google\.com|teams\.(?:live|microsoft)\.com)\/[^\s\\]+/)?.[0] || "";
  const participants = lines.filter((line) => line.startsWith("ATTENDEE")).map((line) => {
    const email = line.match(/mailto:([^;\s]+)/i)?.[1] || "";
    const name = line.match(/CN=(?:"([^"]+)"|([^;:]+))/i)?.slice(1).find(Boolean) || email.split("@")[0];
    return { name: name.replace(/\\,/g, ",").trim(), email: email.toLowerCase() };
  }).filter((item, index, items) => item.email && items.findIndex((other) => other.email === item.email) === index);
  const date = value("DTSTART")?.replace(/Z$/, "");
  const scheduledAt = /^\d{8}T\d{6}$/.test(date || "") ? `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}T${date.slice(9, 11)}:${date.slice(11, 13)}` : "";
  return { title: value("SUMMARY")?.replace(/\\,/g, ",") || "", meetingUrl, scheduledAt, participants };
}
