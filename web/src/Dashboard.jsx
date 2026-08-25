import { useEffect, useState } from "react";

import { api } from "./api";

const dateLabel = (value) => new Date(value).toLocaleDateString("fr-FR", {
  day: "numeric",
  month: "short",
});

export function Dashboard({ user, onNewBot, onOpen }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { api.workspaceOverview().then(setData).catch((err) => setError(err.message)); }, []);
  const firstName = (user.full_name || "vous").split(" ")[0];

  return <section className="page dashboard-page">
    <header className="dashboard-header">
      <div><span className="eyebrow">Espace de travail</span><h1>Bonjour {firstName},</h1><p>Chaque réunion devient une suite de décisions claires.</p></div>
      <button className="primary-button dashboard-cta" onClick={onNewBot}><span>＋</span> Inviter Scribe</button>
    </header>
    {error && <div className="alert error">{error}</div>}
    <div className="metric-grid">
      <Metric value={data?.meetings ?? "—"} label="Réunions captées" tone="sage" />
      <Metric value={data?.captured_minutes ?? "—"} label="Minutes analysées" tone="sand" />
      <Metric value={data?.decisions ?? "—"} label="Décisions isolées" tone="blue" />
      <Metric value={data?.actions?.length ?? "—"} label="Actions à suivre" tone="rose" />
    </div>
    <div className="dashboard-grid">
      <article className="dashboard-panel recent-panel">
        <div className="panel-heading"><div><span className="card-label">Activité</span><h2>Réunions récentes</h2></div><span className="live-count">{data?.live || 0} en direct</span></div>
        {!data ? <Skeleton rows={3}/> : data.recent.length ? data.recent.map((item) =>
          <button className="meeting-line" key={`${item.source}-${item.id}`} onClick={() => onOpen(item)}>
            <span className={`platform-tile ${item.platform}`}><PlatformMark platform={item.platform}/></span>
            <span className="meeting-line-copy"><strong>{item.title}</strong><small>{item.source === "bot" ? "Assistant en ligne" : "Dictaphone"} · {dateLabel(item.created_at)}</small></span>
            <span className={`status ${item.status}`}>{statusLabel(item.status)}</span><span className="arrow">↗</span>
          </button>) : <Empty title="Aucune réunion" text="Invitez Scribe dans un Meet ou un Teams pour commencer."/>}
      </article>
      <article className="dashboard-panel action-panel">
        <div className="panel-heading"><div><span className="card-label">Focus</span><h2>Prochaines actions</h2></div></div>
        {!data ? <Skeleton rows={3}/> : data.actions.length ? data.actions.slice(0, 4).map((action, index) =>
          <div className="action-line" key={`${action.meeting_id}-${index}`}>
            <span className={`priority-dot ${action.priority || "medium"}`}/>
            <div><strong>{action.task}</strong><small>{action.owner || "Responsable à confirmer"}{action.due_date ? ` · ${action.due_date}` : ""}</small></div>
          </div>) : <Empty title="Tout est à jour" text="Les actions explicites apparaîtront automatiquement ici."/>}
      </article>
    </div>
    <article className="bot-banner">
      <div><span className="eyebrow">Assistant de réunion</span><h2>Meet ou Teams : collez le lien, Scribe fait le reste.</h2><p>Consentement vérifié, transcription attribuée aux intervenants, décisions et actions prêtes à partager.</p></div>
      <div className="bot-orbit" aria-hidden="true"><span>S</span><i/><i/><i/></div>
    </article>
  </section>;
}

export function ActionsView() {
  const [data, setData] = useState(null);
  useEffect(() => { api.workspaceOverview().then(setData); }, []);
  return <section className="page"><header className="page-header"><div><span className="eyebrow">Suivi</span><h1>Plan d’action</h1><p>Les engagements explicites, regroupés sans interprétation.</p></div></header><div className="dashboard-panel action-board">{!data ? <Skeleton rows={5}/> : data.actions.length ? data.actions.map((action, index) => <div className="action-line large" key={`${action.meeting_id}-${index}`}><span className={`priority-dot ${action.priority || "medium"}`}/><div><strong>{action.task}</strong><small>{action.meeting_title} · {action.owner || "Responsable à confirmer"}{action.due_date ? ` · Échéance ${action.due_date}` : ""}</small></div><span className="action-priority">{action.priority || "normal"}</span></div>) : <Empty title="Aucune action détectée" text="Scribe n’invente jamais une tâche qui n’a pas été formulée."/>}</div></section>;
}

function Metric({ value, label, tone }) { return <article className={`metric-card ${tone}`}><strong>{value}</strong><span>{label}</span><i/></article>; }
function Skeleton({ rows }) { return <div className="skeleton-list">{Array.from({ length: rows }, (_, index) => <span key={index}/>)}</div>; }
function Empty({ title, text }) { return <div className="panel-empty"><strong>{title}</strong><p>{text}</p></div>; }
function PlatformMark({ platform }) { return <>{platform === "google_meet" ? "M" : platform === "teams" ? "T" : "●"}</>; }
function statusLabel(status) { return ({ joining: "Connexion", live: "En direct", finalizing: "Analyse", completed: "Terminé", stopped: "Arrêté", failed: "Échec", processing: "Analyse", uploaded: "Envoyé" })[status] || status; }
