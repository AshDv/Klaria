import { useEffect, useMemo, useState } from "react";

import { api } from "./api";
import { parisDate, parisDateTime, parisDayKey, parisTime } from "./dateTime";
import { PlatformIcon } from "./PlatformIcon";

const PAGE_SIZE = 8;
const providerLabel = (provider) => provider === "google" ? "Google Calendar" : "Microsoft Outlook";
const platformLabel = (platform) => ({
  google_meet: "Google Meet",
  teams: "Microsoft Teams",
  in_person: "Présentiel",
})[platform] || "Réunion";
const dateTime = (value) => parisDateTime(value);
const dayKey = parisDayKey;
const dayLabel = (value) => parisDate(value, {
  weekday: "long",
  day: "numeric",
  month: "long",
});

export function MeetingsHub({ onNew, onOpenRecording, onOpenRemote }) {
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [history, setHistory] = useState(null);
  const [section, setSection] = useState("upcoming");
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState("all");
  const [display, setDisplay] = useState("calendar");
  const [month, setMonth] = useState(() => new Date());
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [visible, setVisible] = useState(PAGE_SIZE);
  const [showConnections, setShowConnections] = useState(false);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState(new URLSearchParams(location.search).get("calendar_error") || "");

  async function load() {
    try {
      const [nextStatus, nextEvents, remote, recordings] = await Promise.all([
        api.calendarStatus(),
        api.calendarEvents(),
        api.listRemoteMeetings(),
        api.listRecordings(),
      ]);
      setStatus(nextStatus);
      setEvents(nextEvents.filter((item) => item.status !== "cancelled"));
      setHistory([
        ...remote.map((item) => ({ ...item, source: "bot" })),
        ...recordings.map((item) => ({ ...item, source: "dictaphone", platform: "in_person" })),
      ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)));
    } catch (err) { setError(err.message); }
  }

  useEffect(() => { load(); }, []);
  useEffect(() => { setVisible(PAGE_SIZE); }, [section, query, platform]);

  async function connect(provider) {
    setBusy(provider); setError("");
    try {
      const { url } = await api.connectCalendar(provider);
      location.assign(url);
    } catch (err) { setError(err.message); setBusy(""); }
  }

  async function sync() {
    setBusy("sync"); setError(""); setMessage("");
    try {
      const result = await api.syncCalendars();
      setMessage(`${result.synced} réunion(s) synchronisée(s).`);
      if (result.errors.length) setError(result.errors.map((item) => item.message).join(" "));
      await load();
    } catch (err) { setError(err.message); } finally { setBusy(""); }
  }

  async function toggle(event) {
    if (!event.auto_join && !confirm(
      "Activer Scribe ? Les invités recevront une demande de consentement. Le bot attendra tous les accords.",
    )) return;
    setBusy(event.id); setError("");
    try {
      const updated = await api.configureCalendarEvent(event.id, !event.auto_join);
      setEvents((items) => items.map((item) => item.id === updated.id ? updated : item));
    } catch (err) { setError(err.message); } finally { setBusy(""); }
  }

  async function disconnect(connection) {
    if (!confirm(`Déconnecter ${providerLabel(connection.provider)} ?`)) return;
    setBusy(connection.id);
    try { await api.disconnectCalendar(connection.id); await load(); }
    catch (err) { setError(err.message); } finally { setBusy(""); }
  }

  const source = section === "upcoming" ? events : (history || []);
  const filtered = useMemo(() => source.filter((item) => {
    const matchesQuery = `${item.title} ${item.attendees?.map((person) => person.name).join(" ") || ""}`
      .toLocaleLowerCase("fr").includes(query.trim().toLocaleLowerCase("fr"));
    return matchesQuery && (platform === "all" || item.platform === platform);
  }), [source, query, platform]);
  const shown = filtered.slice(0, visible);
  const grouped = shown.reduce((groups, item) => {
    const value = item.starts_at || item.created_at;
    const key = dayKey(value);
    return { ...groups, [key]: [...(groups[key] || []), item] };
  }, {});
  const connected = status?.connections.filter((item) => item.active) || [];

  return <section className="page meetings-hub">
    <header className="page-header meetings-header">
      <div><span className="eyebrow">Espace central</span><h1>Réunions</h1><p>Préparez les prochaines réunions et retrouvez les comptes rendus terminés.</p></div>
      <button className="primary-button" onClick={onNew}>＋ Inviter Scribe</button>
    </header>
    {error && <div className="alert error">{error}</div>}
    {message && <div className="alert success">{message}</div>}

    <div className="meeting-hub-tabs" role="tablist" aria-label="Type de réunion">
      <button className={section === "upcoming" ? "active" : ""} onClick={() => setSection("upcoming")}>
        À venir <span>{events.length}</span>
      </button>
      <button className={section === "history" ? "active" : ""} onClick={() => setSection("history")}>
        Comptes rendus <span>{history?.length || 0}</span>
      </button>
    </div>

    {section === "upcoming" && <>
      <div className="calendar-summary">
        <div className="calendar-summary-copy">
          <span className="calendar-stack" aria-hidden="true"><i><PlatformIcon platform="google" decorative/></i><i><PlatformIcon platform="teams" decorative/></i></span>
          <div><strong>{connected.length ? `${connected.length} agenda(s) connecté(s)` : "Connectez votre agenda"}</strong><small>{connected.length ? "Titres, horaires et invités sont récupérés automatiquement." : "Scribe détectera vos réunions Meet et Teams."}</small></div>
        </div>
        <div className="calendar-summary-actions">
          <button className="text-button inline" onClick={() => setShowConnections(!showConnections)}>{showConnections ? "Fermer" : "Gérer"}</button>
          <button className="secondary-button" onClick={sync} disabled={busy === "sync" || !connected.length}>{busy === "sync" ? "Synchronisation…" : "Actualiser"}</button>
        </div>
      </div>
      {showConnections && <div className="calendar-connectors compact-connectors">
        {["google", "microsoft"].map((provider) => {
          const connection = connected.find((item) => item.provider === provider);
          const available = status?.[`${provider}_available`];
          return <article className={`connector-card ${connection ? "connected" : ""}`} key={provider}>
            <span className={`connector-logo ${provider}`}><PlatformIcon platform={provider} decorative/></span>
            <div><h3>{providerLabel(provider)}</h3><p>{connection ? connection.account_email : available ? "Prêt à être connecté" : "Configuration requise"}</p></div>
            {connection
              ? <button className="text-button" onClick={() => disconnect(connection)} disabled={busy === connection.id}>Déconnecter</button>
              : <button className="secondary-button" onClick={() => connect(provider)} disabled={!available || busy === provider}>{busy === provider ? "Ouverture…" : "Connecter"}</button>}
          </article>;
        })}
      </div>}
    </>}

    <div className="meeting-toolbar">
      <label className="meeting-search"><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher une réunion ou une personne" aria-label="Rechercher une réunion" /></label>
      <label className="meeting-filter"><span>Plateforme</span><select value={platform} onChange={(event) => setPlatform(event.target.value)}><option value="all">Toutes</option><option value="teams">Teams</option><option value="google_meet">Google Meet</option>{section === "history" && <option value="in_person">Présentiel</option>}</select></label>
    </div>

    {section === "upcoming" && <div className="meeting-view-switch" role="group" aria-label="Affichage des réunions">
      <button className={display === "calendar" ? "active" : ""} onClick={() => setDisplay("calendar")}>Calendrier</button>
      <button className={display === "list" ? "active" : ""} onClick={() => setDisplay("list")}>Liste</button>
    </div>}

    {history === null || status === null ? <div className="loading"><span className="large-spinner"/><p>Chargement…</p></div>
      : !filtered.length ? <div className="empty-card meeting-empty"><strong>{query || platform !== "all" ? "Aucun résultat" : section === "upcoming" ? "Aucune réunion à venir" : "Aucun compte rendu"}</strong><p>{query || platform !== "all" ? "Modifiez la recherche ou le filtre." : section === "upcoming" ? "Actualisez vos agendas ou invitez Scribe manuellement." : "Vos réunions terminées apparaîtront ici."}</p>{section === "upcoming" && !query && <button className="primary-button compact" onClick={onNew}>Inviter Scribe</button>}</div>
      : section === "upcoming" && display === "calendar" ? <CalendarMonth
          events={filtered}
          month={month}
          selected={filtered.find((item) => item.id === selectedEvent) || null}
          busy={busy}
          onMonth={setMonth}
          onSelect={setSelectedEvent}
          onToggle={toggle}
        />
      : <div className="meeting-groups">
        {Object.entries(grouped).map(([key, items]) => <section className="meeting-day" key={key}>
          <div className="meeting-day-heading"><h2>{dayLabel(key)}</h2><span>{items.length} réunion{items.length > 1 ? "s" : ""}</span></div>
          <div className="meeting-cards">{items.map((item) => section === "upcoming"
            ? <UpcomingMeeting key={item.id} item={item} busy={busy === item.id} onToggle={() => toggle(item)} />
            : <HistoryMeeting key={`${item.source}-${item.id}`} item={item} onOpen={() => item.source === "bot" ? onOpenRemote(item.id) : onOpenRecording(item.id)} />)}</div>
        </section>)}
        {visible < filtered.length && <button className="load-more" onClick={() => setVisible((count) => count + PAGE_SIZE)}>Afficher {Math.min(PAGE_SIZE, filtered.length - visible)} réunion(s) de plus</button>}
      </div>}
  </section>;
}

function CalendarMonth({ events, month, selected, busy, onMonth, onSelect, onToggle }) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const gridStart = new Date(first);
  gridStart.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  const days = Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart);
    date.setDate(gridStart.getDate() + index);
    return date;
  });
  const eventsByDay = events.reduce((result, item) => {
    const key = localDayKey(item.starts_at);
    result[key] = [...(result[key] || []), item];
    return result;
  }, {});
  const move = (offset) => onMonth(new Date(month.getFullYear(), month.getMonth() + offset, 1));
  const today = localDayKey(new Date());

  return <div className="month-calendar">
    <div className="month-calendar-head">
      <div><span className="eyebrow">Agenda</span><h2>{month.toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}</h2></div>
      <div className="month-navigation">
        <button onClick={() => move(-1)} aria-label="Mois précédent">←</button>
        <button onClick={() => onMonth(new Date())}>Aujourd’hui</button>
        <button onClick={() => move(1)} aria-label="Mois suivant">→</button>
      </div>
    </div>
    <div className="month-scroll">
      <div className="month-grid" role="grid" aria-label={month.toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}>
        {["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"].map((day) => <div className="month-weekday" role="columnheader" key={day}>{day}</div>)}
        {days.map((date) => {
          const key = localDayKey(date);
          const items = eventsByDay[key] || [];
          return <div className={`month-day ${date.getMonth() !== month.getMonth() ? "outside" : ""} ${key === today ? "today" : ""}`} role="gridcell" key={key}>
            <span className="month-day-number">{date.getDate()}</span>
            <div className="month-day-events">{items.slice(0, 3).map((item) => <button className={`month-event ${item.platform}`} key={item.id} onClick={() => onSelect(item.id)} title={item.title}>
              <span>{parisTime(item.starts_at)}</span>
              <strong>{item.title}</strong>
            </button>)}{items.length > 3 && <small>+{items.length - 3} autre{items.length > 4 ? "s" : ""}</small>}</div>
          </div>;
        })}
      </div>
    </div>
    {selected && <CalendarEventPanel item={selected} busy={busy === selected.id} onClose={() => onSelect(null)} onToggle={() => onToggle(selected)} />}
  </div>;
}

function CalendarEventPanel({ item, busy, onClose, onToggle }) {
  const end = item.ends_at || null;
  return <aside className="calendar-event-panel" aria-label={`Détails de ${item.title}`}>
    <div className={`meeting-platform ${item.platform}`}><PlatformIcon platform={item.platform} decorative/><small>{parisTime(item.starts_at)}</small></div>
    <div className="calendar-event-panel-copy"><strong>{item.title}</strong><span>{parisDate(item.starts_at, { weekday: "long", day: "numeric", month: "long" })}{end ? `, ${parisTime(item.starts_at)} à ${parisTime(end)}` : ""}</span><small>{platformLabel(item.platform)} · heure de Paris · {item.attendees.length} invité(s) · {item.consent_session_id ? "Accords envoyés" : "Accords à préparer"}</small></div>
    <label className="automation-switch"><input type="checkbox" checked={item.auto_join} disabled={busy} onChange={onToggle}/><span/><em>{item.auto_join ? "Auto" : "Manuel"}</em></label>
    <button className="icon-button" onClick={onClose} aria-label="Fermer les détails">×</button>
  </aside>;
}

function UpcomingMeeting({ item, busy, onToggle }) {
  const time = parisTime(item.starts_at);
  return <article className="meeting-card upcoming-meeting">
    <div className={`meeting-platform ${item.platform}`}><PlatformIcon platform={item.platform} decorative/><small>{time}</small></div>
    <div className="meeting-card-copy"><strong>{item.title}</strong><span>{platformLabel(item.platform)} · {item.attendees.length} invité(s)</span></div>
    <div className="meeting-consent"><strong>{item.consent_session_id ? "Accords envoyés" : "À préparer"}</strong><span>{item.remote_meeting_id ? "Scribe est lancé" : item.auto_join ? "Lancement automatique" : "Lancement manuel"}</span></div>
    <label className="automation-switch"><input type="checkbox" checked={item.auto_join} disabled={busy} onChange={onToggle}/><span/><em>{item.auto_join ? "Auto" : "Manuel"}</em></label>
  </article>;
}

function HistoryMeeting({ item, onOpen }) {
  return <button className="meeting-card history-meeting" onClick={onOpen}>
    <span className={`meeting-platform ${item.platform}`}><PlatformIcon platform={item.platform} decorative/></span>
    <span className="meeting-card-copy"><strong>{item.title}</strong><span>{platformLabel(item.platform)} · {dateTime(item.created_at)}</span></span>
    <span className={`status ${item.status}`}>{statusLabel(item.status)}</span>
    <span className="meeting-arrow" aria-hidden="true">→</span>
  </button>;
}

function statusLabel(status) {
  return ({ joining: "Connexion", live: "En direct", finalizing: "Analyse", completed: "Terminé", stopped: "Arrêté", failed: "Échec", processing: "Analyse", uploaded: "Envoyé" })[status] || status;
}

const localDayKey = parisDayKey;
