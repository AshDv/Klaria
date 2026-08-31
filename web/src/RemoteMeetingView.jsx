import { useEffect, useMemo, useState } from "react";

import { api, remoteMeetingSocket } from "./api";
import { parisDateTime } from "./dateTime";
import { MeetingReplay } from "./MeetingReplay";
import { PlatformIcon } from "./PlatformIcon";
import { PodcastPlayer } from "./PodcastPlayer";

const statusLabels = { joining: "En attente d’admission", live: "En direct", finalizing: "Création du compte rendu", completed: "Terminé", failed: "Échec", stopped: "Arrêté" };

export function RemoteMeetingView({ id, onBack }) {
  const [meeting, setMeeting] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const current = meeting?.status;
        const data = ["joining", "live"].includes(current) ? await api.syncRemoteMeeting(id) : await api.getRemoteMeeting(id);
        if (active) { setMeeting(data); setError(data.sync_warning || ""); }
      } catch (err) { if (active) setError(err.message); }
    };
    load();
    const timer = setInterval(load, ["completed", "failed", "stopped"].includes(meeting?.status) ? 30000 : 6000);
    return () => { active = false; clearInterval(timer); };
  }, [id, meeting?.status]);

  useEffect(() => {
    if (!["joining", "live"].includes(meeting?.status)) return undefined;
    const socket = remoteMeetingSocket(id);
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "transcript" && data.segments.length) {
        setMeeting((current) => ({ ...current, status: "live", segments: mergeSegments(current.segments, data.segments) }));
      }
      if (data.type === "status" && data.status === "stopped") {
        api.getRemoteMeeting(id).then(setMeeting).catch((err) => setError(err.message));
      }
    };
    return () => socket.close();
  }, [id, meeting?.status]);

  async function finish() {
    setMeeting(await api.finishRemoteMeeting(id));
  }

  async function stopNow() {
    if (!confirm("Arrêter Nolya et effacer définitivement toutes les données de ce direct ?")) return;
    setMeeting(await api.stopRemoteMeeting(id));
  }

  async function reanalyze() {
    setMeeting(await api.reanalyzeRemoteMeeting(id));
  }

  async function remove() {
    if (!confirm("Supprimer définitivement cette réunion et son compte rendu ?")) return;
    await api.deleteRemoteMeeting(id); onBack();
  }

  if (!meeting) return <div className="loading"><span className="large-spinner"/><p>Connexion à la réunion…</p></div>;
  return <section className="page remote-page">
    <button className="back-button" onClick={onBack}>← Toutes les réunions</button>
    <header className="remote-header">
      <div><div className="remote-meta"><span className={`status ${meeting.status}`}>{statusLabels[meeting.status]}</span><span className={`platform-chip ${meeting.platform}`}><PlatformIcon platform={meeting.platform} decorative/>{meeting.platform === "google_meet" ? "Google Meet" : "Microsoft Teams"}</span></div><h1>{meeting.title}</h1><p>{formatDate(meeting.created_at)} · {formatDuration(meeting.duration_seconds)}</p></div>
      <div className="remote-actions">{meeting.segments?.length > 0 && ["completed", "failed"].includes(meeting.status) && <button className="secondary-button" onClick={reanalyze}>Nettoyer et réanalyser</button>}{["joining", "live"].includes(meeting.status) && <button className="secondary-button" onClick={stopNow}>Arrêter et effacer</button>}{meeting.status === "live" && <button className="stop-button" onClick={finish}>Terminer et analyser</button>}<button className="icon-button danger" onClick={remove} aria-label="Supprimer">×</button></div>
    </header>
    {error && <div className="alert error">{error}</div>}
    {meeting.status === "joining" && <Joining meeting={meeting}/>}
    {meeting.status === "live" && <LiveRoom meeting={meeting}/>}
    {meeting.status === "finalizing" && <Finalizing meeting={meeting}/>}
    {meeting.status === "completed" && <MeetingReport meeting={meeting} onChange={setMeeting}/>}
    {meeting.status === "failed" && <div className="processing-card error-state"><h2>La réunion n’a pas pu être traitée</h2><p>{meeting.error}</p></div>}
    {meeting.status === "stopped" && <div className="processing-card"><h2>Traitement arrêté</h2><p>{meeting.error || "Le consentement a été retiré."}</p></div>}
  </section>;
}

function Joining({ meeting }) { return <div className="joining-layout"><article className="joining-card"><div className="bot-avatar"><span>S</span><i/></div><span className="eyebrow">Nolya demande à entrer</span><h2>Admettez le bot dans {meeting.platform === "google_meet" ? "Google Meet" : "Microsoft Teams"}</h2><p>Il apparaîtra sous le nom « Nolya — prise de notes ». La transcription commencera dès son admission.</p><div className="waiting-line"><span className="spinner"/> En attente de l’hôte</div></article><aside className="content-card admission-check"><span className="card-label">À vérifier</span><ol><li>La réunion est déjà ouverte.</li><li>L’hôte voit la demande de Nolya.</li><li>Tous les participants savent que le bot transcrit.</li></ol></aside></div>; }

function LiveRoom({ meeting }) {
  const speakers = new Set(meeting.segments.map((item) => item.speaker)).size;
  return <div className="live-layout"><main className="live-transcript"><div className="live-heading"><div><span className="live-pulse"/>Transcription en direct</div><span>{meeting.segments.length} passages</span></div><div className="transcript-stream">{meeting.segments.length ? meeting.segments.map((segment) => <div className="speech-row" key={segment.id}><span className="speaker-avatar">{segment.speaker.slice(0, 1).toUpperCase()}</span><div><strong>{segment.speaker}<small>{formatClock(segment.start)}</small>{segment.speaker_mapping_status === "NO_SPEAKER_EVENTS" && <em>identité incertaine</em>}</strong><p>{segment.text}</p></div></div>) : <div className="listening-empty"><span className="sound-ring"/><h3>Nolya écoute</h3><p>Les premières phrases vont apparaître ici.</p></div>}</div></main><aside className="live-rail"><article><span className="card-label">Session</span><strong>{formatDuration(meeting.duration_seconds)}</strong><small>temps capté</small></article><article><span className="card-label">Voix</span><strong>{speakers || "—"}</strong><small>intervenants détectés</small></article><article className="chat-control"><span className="card-label">Contrôle dans le chat</span><strong>STOP NOLYA</strong><small>arrête immédiatement la capture. Si l’auteur est identifié, ses passages et les passages incertains sont supprimés ; sinon tout est effacé.</small></article><article className="privacy-live"><span>✓</span><div><strong>{meeting.media_recording_enabled ? "Replay audio autorisé" : "Audio non conservé"}</strong><small>{meeting.media_recording_enabled ? `Suppression après ${meeting.media_retention_days} jour${meeting.media_retention_days > 1 ? "s" : ""}.` : "Seul le texte utile est gardé."}</small></div></article></aside></div>;
}

function Finalizing({ meeting }) { return <div className="analysis-stage"><div className="analysis-orbit"><span>S</span><i/><i/><i/></div><span className="eyebrow">Analyse en cours</span><h2>Nolya relie chaque décision à ses preuves</h2><p>{meeting.segments.length} passages sont organisés en résumé, décisions, actions, risques et brief audio.</p><div className="skill-pills">{meeting.skills.map((skill) => <span key={skill.key}>✓ {skill.title}</span>)}</div></div>; }

function MeetingReport({ meeting, onChange }) {
  const [tab, setTab] = useState("replay");
  const report = meeting.report;
  const mentions = report.mentions || [];
  const speakerNames = useMemo(() => Object.fromEntries((report.speakers || []).map((item) => [item.label, item.participant_name || item.label])), [report.speakers]);
  return <>
    <div className="report-tabs"><button className={tab === "replay" ? "active" : ""} onClick={() => setTab("replay")}>Replay</button><button className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}>Synthèse</button><button className={tab === "decisions" ? "active" : ""} onClick={() => setTab("decisions")}>Décisions <span>{report.decisions.length}</span></button><button className={tab === "actions" ? "active" : ""} onClick={() => setTab("actions")}>Actions <span>{report.actions.length}</span></button><button className={tab === "mentions" ? "active" : ""} onClick={() => setTab("mentions")}>Mentions <span>{mentions.length}</span></button><button className={tab === "transcript" ? "active" : ""} onClick={() => setTab("transcript")}>Transcript</button></div>
    {tab === "replay" && <MeetingReplay meeting={meeting}/>}
    {tab === "overview" && <div className="report-overview"><article className="executive-card"><span className="card-label">En bref</span><RichText value={report.executive_summary}/><div className="report-facts"><span><strong>{report.decisions.length}</strong> décisions</span><span><strong>{report.actions.length}</strong> actions</span><span><strong>{report.open_questions.length}</strong> questions ouvertes</span></div></article>{report.quality && <article className="quality-card"><div><strong>{report.quality.coverage_percent}%</strong><span>transcript couvert</span></div><div><strong>{report.quality.source_linked_facts_percent}%</strong><span>faits sourcés</span></div><div><strong>{report.quality.identified_speakers_percent}%</strong><span>voix identifiées</span></div></article>}<PostMeetingTools meeting={meeting}/><PodcastPlayer script={report.podcast_script} meetingId={meeting.id} overview={report.podcast_overview}/><article className="content-card minutes-card"><span className="card-label">Compte rendu détaillé</span><RichText value={report.detailed_minutes}/></article><InsightList title="Points clés" items={report.key_points} render={(item) => <><strong>{item.topic}</strong><p>{item.detail}</p></>}/><InsightList title="Risques et vigilances" items={report.risks} render={(item) => <><strong>{item.risk}</strong><p>{item.mitigation || "Aucune réponse définie pendant la réunion."}</p></>}/></div>}
    {tab === "decisions" && <div className="decision-board">{report.decisions.length ? report.decisions.map((item, index) => <article className="decision-card" key={index}><div><span className={`decision-state ${item.status}`}>{decisionLabel(item.status)}</span><small>Décision {String(index + 1).padStart(2, "0")}</small></div><h3>{item.decision}</h3>{item.rationale && <p>{item.rationale}</p>}<footer>{item.decided_by.length ? `Portée par ${item.decided_by.map((name) => speakerNames[name] || name).join(", ")}` : "Auteur non précisé"}</footer></article>) : <EmptySection text="Aucune décision explicite n’a été formulée."/>}</div>}
    {tab === "actions" && <div className="action-table"><div className="action-table-head"><span>Action</span><span>Responsable</span><span>Échéance</span><span>Priorité</span></div>{report.actions.length ? report.actions.map((item, index) => <ActionEditor key={index} meeting={meeting} action={item} index={index} onChange={onChange}/>) : <EmptySection text="Aucune action explicite n’a été formulée."/>}</div>}
    {tab === "mentions" && <div className="mention-board">{mentions.length ? mentions.map((item, index) => <article className="mention-card" key={index}><span className="mention-symbol">@</span><div><strong>{item.mentioned_person}</strong><small>Mentionné par {speakerNames[item.speaker] || item.speaker}</small><p>{item.context}</p><footer>Passage{item.segment_ids.length > 1 ? "s" : ""} {item.segment_ids.map((id) => `#${id + 1}`).join(", ")}</footer></div></article>) : <EmptySection text="Aucune personne n’a été directement nommée."/>}</div>}
    {tab === "transcript" && <div className="content-card transcript-full"><div className="transcript-toolbar"><span className="card-label">Transcription diarisée</span><span>{report.coverage.length}/{meeting.segments.length} passages vérifiés</span></div>{meeting.segments.map((segment) => <div className="speech-row" key={segment.id}><span className="speaker-avatar">{segment.speaker.slice(0, 1).toUpperCase()}</span><div><strong>{speakerNames[segment.speaker] || segment.speaker}<small>{formatClock(segment.start)}</small></strong><p>{segment.text}</p></div></div>)}</div>}
    <p className={`provider-cleanup ${meeting.provider_data_deleted ? "done" : "pending"}`}>{meeting.provider_data_deleted ? "✓ Les données temporaires du bot ont été supprimées après traitement." : "Suppression des données temporaires du bot en cours."} {meeting.recap_posted && "Le récapitulatif a aussi été publié dans le chat."}</p>
  </>;
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

function ActionEditor({ meeting, action, index, onChange }) {
  const [draft, setDraft] = useState({
    owner_email: action.owner_email || "",
    due_date: action.due_date || "",
    priority: action.priority || "medium",
  });
  const [saving, setSaving] = useState(false);
  async function save() {
    setSaving(true);
    try {
      await api.updateMeetingAction(meeting.id, index, {
        owner_email: draft.owner_email || null,
        due_date: draft.due_date || null,
        priority: draft.priority || null,
      });
      onChange(await api.getRemoteMeeting(meeting.id));
    } finally { setSaving(false); }
  }
  return <div className="action-table-row editable">
    <strong>{action.task}</strong>
    <select aria-label={`Responsable de ${action.task}`} value={draft.owner_email} onChange={(event) => setDraft({ ...draft, owner_email:event.target.value })}>
      <option value="">Non attribuée</option>
      {meeting.participants.filter((item) => item.active).map((item) => <option key={item.email} value={item.email}>{item.name}</option>)}
    </select>
    <input aria-label={`Échéance de ${action.task}`} type="date" value={draft.due_date} onChange={(event) => setDraft({ ...draft, due_date:event.target.value })}/>
    <div className="action-save"><select aria-label={`Priorité de ${action.task}`} value={draft.priority} onChange={(event) => setDraft({ ...draft, priority:event.target.value })}><option value="low">Basse</option><option value="medium">Normale</option><option value="high">Haute</option></select><button onClick={save} disabled={saving}>{saving ? "…" : "Enregistrer"}</button></div>
  </div>;
}

function PostMeetingTools({ meeting }) {
  const participants = meeting.participants.filter((item) => item.active);
  const [selected, setSelected] = useState(participants.map((item) => item.email));
  const [title, setTitle] = useState(`Suivi — ${meeting.title}`);
  const [startsAt, setStartsAt] = useState("");
  const [message, setMessage] = useState("");
  const toggle = (email) => setSelected((items) => items.includes(email) ? items.filter((item) => item !== email) : [...items, email]);
  async function share() {
    try { const data = await api.shareMeetingReport(meeting.id, selected); setMessage(`${data.sent} compte rendu envoyé.`); }
    catch (error) { setMessage(error.message); }
  }
  async function schedule() {
    try {
      const data = await api.createMeetingFollowUp(meeting.id, { title, starts_at:new Date(startsAt).toISOString(), duration_minutes:30, participant_emails:selected });
      setMessage(`Réunion créée${data.meeting_url ? " avec lien de visioconférence" : ""}.`);
    } catch (error) { setMessage(error.message); }
  }
  return <article className="content-card post-meeting-tools"><span className="card-label">Après la réunion</span><h3>Partager ou organiser le suivi</h3><div className="participant-picks">{participants.map((item) => <label key={item.email}><input type="checkbox" checked={selected.includes(item.email)} onChange={() => toggle(item.email)}/><span>{item.name}<small>{item.email}</small></span></label>)}</div><div className="post-actions"><button className="secondary-button" onClick={share} disabled={!selected.length}>Envoyer le compte rendu</button><input aria-label="Titre de la réunion de suivi" value={title} onChange={(event) => setTitle(event.target.value)}/><input aria-label="Date et heure du suivi" type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)}/><button className="primary-button" onClick={schedule} disabled={!selected.length || !startsAt}>Créer et inviter</button></div>{message && <p className="form-feedback">{message}</p>}<small>La création reste confirmée par un utilisateur : Nolya ne programme jamais une réunion sur une simple supposition du modèle.</small></article>;
}

function InsightList({ title, items, render }) { return <article className="content-card insight-list"><span className="card-label">{title}</span>{items.length ? items.map((item, index) => <div className="insight-row" key={index}>{render(item)}</div>) : <p className="muted">Aucun élément identifié.</p>}</article>; }
function EmptySection({ text }) { return <div className="panel-empty"><strong>Rien à afficher</strong><p>{text}</p></div>; }
function formatDate(value) { return parisDateTime(value, "long"); }
function formatDuration(seconds = 0) { return `${Math.floor(seconds / 60)} min ${String(seconds % 60).padStart(2, "0")} s`; }
function formatClock(seconds = 0) { return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`; }
function decisionLabel(status) { return ({ confirmed: "Confirmée", proposed: "Proposée", deferred: "Reportée" })[status] || status; }
function priorityLabel(priority) { return ({ high: "Haute", medium: "Normale", low: "Basse" })[priority] || "Normale"; }
function mergeSegments(current = [], incoming = []) {
  const clean = (text) => text.toLocaleLowerCase("fr").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  const segments = [...current];
  incoming.forEach((candidate) => {
    const text = clean(candidate.text);
    const index = segments.findIndex((item) => {
      const previous = clean(item.text);
      return item.speaker === candidate.speaker && Math.abs(item.start - candidate.start) <= 2 && (previous.includes(text) || text.includes(previous));
    });
    if (index < 0) segments.push(candidate);
    else if (text.length >= clean(segments[index].text).length) segments[index] = { ...segments[index], ...candidate };
  });
  return segments
    .sort((left, right) => String(left.absolute_start_time || left.start).localeCompare(String(right.absolute_start_time || right.start), undefined, { numeric: true }))
    .map((item, id) => ({ ...item, id }));
}
