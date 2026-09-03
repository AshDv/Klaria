import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "./api";
import { parisDateTime } from "./dateTime";

const palette = ["#167d64", "#4876b8", "#c55f61", "#9a6b2f", "#7656a5", "#258399"];

export function MeetingReplay({ meeting }) {
  const [panel, setPanel] = useState("speakers");
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [mediaUrl, setMediaUrl] = useState("");
  const media = useRef(null);
  const replay = useMemo(() => buildReplay(meeting), [meeting]);
  const active = replay.segments.filter((item) => item.start <= currentTime).slice(-1)[0] || replay.segments[0];

  useEffect(() => {
    if (!meeting.media_available) return undefined;
    let mounted = true;
    api.getRemoteMeetingMedia(meeting.id).then(({ url }) => {
      if (mounted) setMediaUrl(url);
    }).catch(() => {});
    return () => {
      mounted = false;
    };
  }, [meeting.id, meeting.media_available]);

  useEffect(() => {
    if (!playing || media.current) return undefined;
    const timer = setInterval(() => setCurrentTime((value) => {
      const next = Math.min(replay.duration, value + .25);
      if (next >= replay.duration) setPlaying(false);
      return next;
    }), 250);
    return () => clearInterval(timer);
  }, [playing, replay.duration]);

  function seek(value) {
    const next = Math.max(0, Math.min(replay.duration, Number(value)));
    setCurrentTime(next);
    if (media.current) media.current.currentTime = next;
  }

  function toggle() {
    if (media.current) {
      if (media.current.paused) media.current.play();
      else media.current.pause();
      return;
    }
    setPlaying((value) => !value);
  }

  return <div className="replay-layout">
    <section className="replay-stage">
      <div className="replay-screen">
        <div className="replay-screen-meta"><span>Replay de la réunion</span><span>{meeting.media_available ? `Audio conservé avec consentement${meeting.media_expires_at ? ` · suppression ${parisDateTime(meeting.media_expires_at)}` : ""}` : "Reconstruction depuis le transcript"}</span></div>
        <div className="replay-speaker"><span>{initials(active?.speaker)}</span><small>{active?.speaker || "Réunion"}</small><p>{active?.text || "Aucun passage disponible."}</p></div>
        {mediaUrl && <audio ref={media} src={mediaUrl} onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}/>}
        <button className="replay-play" onClick={toggle} aria-label={playing ? "Mettre en pause" : "Lire le replay"}>{playing ? "Ⅱ" : "▶"}</button>
      </div>
      <div className="replay-controls">
        <span>{clock(currentTime)}</span><input aria-label="Position du replay" type="range" min="0" max={replay.duration} step=".1" value={currentTime} onChange={(event) => seek(event.target.value)}/><span>{clock(replay.duration)}</span>
      </div>
      <div className="replay-panels">
        <div className="replay-panel-tabs"><button className={panel === "speakers" ? "active" : ""} onClick={() => setPanel("speakers")}>Intervenants</button><button className={panel === "topics" ? "active" : ""} onClick={() => setPanel("topics")}>Rubriques</button><button className={panel === "chapters" ? "active" : ""} onClick={() => setPanel("chapters")}>Chapitres</button></div>
        {panel === "speakers" && <div className="speaker-timelines">{replay.speakers.map((speaker) => <div className="speaker-timeline" key={speaker.name}><button onClick={() => seek(speaker.ranges[0]?.start || 0)}><span style={{ background:speaker.color }}>{initials(speaker.name)}</span><strong>{speaker.name}</strong><small>{speaker.share}%</small></button><div className="timeline-track">{speaker.ranges.map((range, index) => <i key={index} title={`${speaker.name}, ${clock(range.start)}`} style={{ background:speaker.color, left:`${range.start / replay.duration * 100}%`, width:`${Math.max(.7, (range.end - range.start) / replay.duration * 100)}%` }} onClick={() => seek(range.start)}/>)}</div></div>)}</div>}
        {panel === "topics" && <div className="replay-topic-list">{replay.chapters.map((chapter) => <button key={chapter.id} onClick={() => seek(chapter.start)}><span>{clock(chapter.start)}</span><strong>{chapter.title}</strong><small>{chapter.segmentIds.length} passages</small></button>)}</div>}
        {panel === "chapters" && <div className="replay-chapter-strip">{replay.chapters.map((chapter, index) => <button key={chapter.id} className={currentTime >= chapter.start && currentTime < chapter.end ? "active" : ""} onClick={() => seek(chapter.start)}><span>{String(index + 1).padStart(2, "0")}</span><strong>{chapter.title}</strong><small>{clock(chapter.start)} à {clock(chapter.end)}</small></button>)}</div>}
      </div>
    </section>
    <aside className="replay-notes">
      <div className="replay-notes-head"><div><span className="card-label">Résumé synchronisé</span><h2>Notes de la réunion</h2></div><span>{replay.chapters.length} chapitres</span></div>
      <p className="replay-warning">Chaque élément renvoie au passage qui le justifie.</p>
      <div className="replay-note-list">{replay.chapters.map((chapter) => <article key={chapter.id} className={currentTime >= chapter.start && currentTime < chapter.end ? "active" : ""}><button onClick={() => seek(chapter.start)}><span>{clock(chapter.start)}</span><div><strong>{chapter.title}</strong><p>{chapter.summary}</p><small>{chapter.segmentIds.length} passage{chapter.segmentIds.length > 1 ? "s" : ""} source</small></div></button></article>)}</div>
      {!!replay.moments.length && <div className="replay-moments"><span className="card-label">Moments clés</span>{replay.moments.map((moment, index) => <button key={`${moment.kind}-${index}`} onClick={() => seek(moment.start)}><span>{moment.label}</span><p>{moment.text}</p><small>{clock(moment.start)}</small></button>)}</div>}
    </aside>
  </div>;
}

function buildReplay(meeting) {
  const raw = meeting.segments || [];
  const absolute = raw.map((item) => Date.parse(item.absolute_start_time) / 1000).filter(Number.isFinite);
  const base = absolute.length ? Math.min(...absolute) : 0;
  const reportSpeakers = meeting.report?.speakers || [];
  const onlyName = reportSpeakers.length === 1 ? reportSpeakers[0].participant_name || reportSpeakers[0].label : "";
  const names = Object.fromEntries(reportSpeakers.map((item) => [item.label, item.participant_name || item.label]));
  const segments = raw.map((item, id) => {
    const absoluteStart = Date.parse(item.absolute_start_time) / 1000;
    const absoluteEnd = Date.parse(item.absolute_end_time) / 1000;
    const numericStart = Number(item.start);
    const relativeStart = Number.isFinite(numericStart) && numericStart < 86400 ? numericStart : absoluteStart - base;
    const start = Math.max(0, Number.isFinite(relativeStart) ? relativeStart : 0);
    const numericEnd = Number(item.end);
    const relativeEnd = Number.isFinite(numericEnd) && numericEnd >= start && numericEnd < 86400 ? numericEnd : absoluteEnd - base;
    const estimate = Math.max(1.5, String(item.text || "").split(/\s+/).length / 2.4);
    const end = Number.isFinite(relativeEnd) && relativeEnd > start ? relativeEnd : start + estimate;
    const generic = ["speaker", "intervenant inconnu", "intervenant non identifié"].includes(String(item.speaker).toLocaleLowerCase("fr"));
    return { ...item, id, start, end, speaker: generic && onlyName ? onlyName : names[item.speaker] || item.speaker };
  }).sort((left, right) => left.start - right.start);
  const duration = Math.max(1, meeting.duration_seconds || 0, ...segments.map((item) => item.end));
  const grouped = segments.reduce((result, item) => {
    const name = item.speaker || "Intervenant non identifié";
    result[name] = [...(result[name] || []), item];
    return result;
  }, {});
  const speakers = Object.entries(grouped).map(([name, items], index) => ({
    name,
    color: palette[index % palette.length],
    ranges: items.map((item) => ({ start:item.start, end:item.end })),
    share: Math.round(items.reduce((sum, item) => sum + item.end - item.start, 0) / duration * 100),
  }));
  const byId = Object.fromEntries(segments.map((item) => [item.id, item]));
  const points = meeting.report?.key_points || [];
  const chapters = (points.length ? points : [{ topic:"Réunion", detail:meeting.report?.executive_summary || "Transcript de la réunion", segment_ids:segments.map((item) => item.id) }]).map((point, index) => {
    const source = (point.segment_ids || []).map((id) => byId[id]).filter(Boolean);
    return { id:index, title:point.topic || `Chapitre ${index + 1}`, summary:point.detail || "", segmentIds:source.map((item) => item.id), start:source.length ? Math.min(...source.map((item) => item.start)) : index / Math.max(1, points.length) * duration };
  }).sort((left, right) => left.start - right.start).map((chapter, index, items) => ({ ...chapter, end:items[index + 1]?.start || duration }));
  const momentGroups = [
    ["Décision", "decision", meeting.report?.decisions, "decision"],
    ["Action", "action", meeting.report?.actions, "task"],
    ["Risque", "risk", meeting.report?.risks, "risk"],
    ["Question", "question", meeting.report?.open_questions, "question"],
  ];
  const moments = momentGroups.flatMap(([label, kind, items = [], field]) => items.map((item) => ({ label, kind, text:item[field], start:byId[item.segment_ids?.[0]]?.start || 0 })));
  return { segments, speakers, chapters, moments, duration };
}

function initials(value = "") { return value.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "S"; }
function clock(seconds = 0) { return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`; }
