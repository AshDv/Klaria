import { useEffect, useState } from "react";

import { api } from "./api";
import { PlatformIcon } from "./PlatformIcon";

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
      <button className="primary-button dashboard-cta" onClick={onNewBot}><span>＋</span> Inviter Nolya</button>
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
          </button>) : <Empty title="Aucune réunion" text="Invitez Nolya dans un Meet ou un Teams pour commencer."/>}
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
      <div><span className="eyebrow">Assistant de réunion</span><h2>Meet ou Teams : collez le lien, Nolya fait le reste.</h2><p>Consentement vérifié, transcription attribuée aux intervenants, décisions et actions prêtes à partager.</p></div>
      <div className="bot-orbit" aria-hidden="true"><span>S</span><i/><i/><i/></div>
    </article>
  </section>;
}

export function ActionsView() {
  const [data, setData] = useState(null);
  const [filters, setFilters] = useState({ query:"", meeting:"all", owner:"all", priority:"all" });
  useEffect(() => { api.workspaceOverview().then(setData); }, []);
  const actions = data?.actions || [];
  const meetings = [...new Map(actions.map((item) => [item.meeting_id, item.meeting_title])).entries()];
  const owners = [...new Set(actions.map((item) => item.owner).filter(Boolean))].sort();
  const visible = actions.filter((item) => {
    const text = `${item.task} ${item.meeting_title} ${item.owner || ""}`.toLocaleLowerCase("fr");
    return (!filters.query || text.includes(filters.query.toLocaleLowerCase("fr")))
      && (filters.meeting === "all" || item.meeting_id === filters.meeting)
      && (filters.owner === "all" || item.owner === filters.owner)
      && (filters.priority === "all" || (item.priority || "medium") === filters.priority);
  });
  return <section className="page"><header className="page-header"><div><span className="eyebrow">Suivi</span><h1>Plan d’action</h1><p>Retrouvez chaque engagement par sujet, réunion, responsable ou priorité.</p></div></header><div className="action-filters"><input aria-label="Rechercher un sujet ou une action" placeholder="Sujet, action ou personne" value={filters.query} onChange={(event) => setFilters({ ...filters, query:event.target.value })}/><select aria-label="Filtrer par réunion" value={filters.meeting} onChange={(event) => setFilters({ ...filters, meeting:event.target.value })}><option value="all">Toutes les réunions</option>{meetings.map(([id, title]) => <option key={id} value={id}>{title}</option>)}</select><select aria-label="Filtrer par responsable" value={filters.owner} onChange={(event) => setFilters({ ...filters, owner:event.target.value })}><option value="all">Tous les responsables</option>{owners.map((owner) => <option key={owner}>{owner}</option>)}</select><select aria-label="Filtrer par priorité" value={filters.priority} onChange={(event) => setFilters({ ...filters, priority:event.target.value })}><option value="all">Toutes les priorités</option><option value="high">Haute</option><option value="medium">Normale</option><option value="low">Basse</option></select></div><div className="action-results"><span>{visible.length} action{visible.length > 1 ? "s" : ""}</span>{filters.query || filters.meeting !== "all" || filters.owner !== "all" || filters.priority !== "all" ? <button onClick={() => setFilters({ query:"", meeting:"all", owner:"all", priority:"all" })}>Réinitialiser</button> : null}</div><div className="dashboard-panel action-board">{!data ? <Skeleton rows={5}/> : visible.length ? visible.map((action, index) => <div className="action-line large" key={`${action.meeting_id}-${index}`}><span className={`priority-dot ${action.priority || "medium"}`}/><div><strong>{action.task}</strong><small>{action.meeting_title} · {action.owner || "Non attribuée"}{action.due_date ? ` · Échéance ${action.due_date}` : ""}</small></div><span className="action-priority">{action.priority || "normal"}</span></div>) : <Empty title="Aucune action trouvée" text="Modifiez les filtres ou ouvrez une réunion pour compléter ses actions."/>}</div></section>;
}

function Metric({ value, label, tone }) { return <article className={`metric-card ${tone}`}><strong>{value}</strong><span>{label}</span><i/></article>; }
function Skeleton({ rows }) { return <div className="skeleton-list">{Array.from({ length: rows }, (_, index) => <span key={index}/>)}</div>; }
function Empty({ title, text }) { return <div className="panel-empty"><strong>{title}</strong><p>{text}</p></div>; }
function PlatformMark({ platform }) { return <PlatformIcon platform={platform} decorative/>; }
function statusLabel(status) { return ({ joining: "Connexion", live: "En direct", finalizing: "Analyse", completed: "Terminé", stopped: "Arrêté", failed: "Échec", processing: "Analyse", uploaded: "Envoyé" })[status] || status; }
