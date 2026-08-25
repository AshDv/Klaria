import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "./api";

const FORMATS = {
  deep_dive: "Conversation",
  brief: "L'essentiel",
  critique: "Revue critique",
  debate: "Débat",
};
const FEMALE = /amelie|audrey|celine|denise|hortense|julie|marie|virginie/i;
const MALE = /henri|nicolas|paul|remy|thomas/i;

export function PodcastPlayer({ script = [], meetingId, overview }) {
  const [turns, setTurns] = useState(script);
  const [meta, setMeta] = useState(overview || null);
  const [playing, setPlaying] = useState(false);
  const [active, setActive] = useState(0);
  const [format, setFormat] = useState("deep_dive");
  const [minutes, setMinutes] = useState(5);
  const [focus, setFocus] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const voices = useRef([]);
  const supported = "speechSynthesis" in window;
  const duration = useMemo(
    () => Math.max(1, Math.round(turns.reduce((sum, item) => sum + item.text.length, 0) / 14)),
    [turns],
  );

  useEffect(() => { setTurns(script); }, [script]);
  useEffect(() => { setMeta(overview || null); }, [overview]);
  useEffect(() => {
    if (!supported) return undefined;
    const load = () => { voices.current = window.speechSynthesis.getVoices(); };
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => {
      window.speechSynthesis.cancel();
      window.speechSynthesis.removeEventListener("voiceschanged", load);
    };
  }, [supported]);

  function selectedVoices() {
    const french = voices.current.filter((voice) => voice.lang.toLowerCase().startsWith("fr"));
    const available = french.length ? french : voices.current;
    const male = available.find((voice) => MALE.test(voice.name)) || available[0];
    const female = available.find((voice) => FEMALE.test(voice.name) && voice !== male)
      || available.find((voice) => voice !== male) || male;
    return { host_a: male, host_b: female };
  }

  function play() {
    if (!supported || !turns.length) return;
    window.speechSynthesis.cancel();
    const selected = selectedVoices();
    turns.forEach((turn, index) => {
      const utterance = new SpeechSynthesisUtterance(turn.text);
      utterance.lang = "fr-FR";
      utterance.rate = 1.02;
      utterance.pitch = turn.host === "host_a" ? 0.94 : 1.06;
      utterance.voice = selected[turn.host] || null;
      utterance.onstart = () => { setActive(index); setPlaying(true); };
      utterance.onend = () => {
        if (index === turns.length - 1) { setPlaying(false); setActive(0); }
      };
      window.speechSynthesis.speak(utterance);
    });
  }

  function stop() {
    window.speechSynthesis.cancel();
    setPlaying(false);
    setActive(0);
  }

  async function generate() {
    setBusy(true); setError(""); stop();
    try {
      const result = await api.createPodcast(meetingId, { format, minutes, focus: focus.trim() || null });
      setMeta(result); setTurns(result.turns);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  if (!turns.length && !meetingId) return null;
  const current = turns[active];
  return <article className="podcast-card">
    <div className="podcast-art" aria-hidden="true">
      <span className="host-dot host-a">T</span><span className="sound-bar"/><span className="sound-bar"/><span className="sound-bar"/><span className="host-dot host-b">C</span>
    </div>
    <div className="podcast-copy">
      <span className="card-label">Brief audio · Thomas & Camille</span>
      <h3>{meta?.title || "La réunion, racontée à deux voix"}</h3>
      <p>{meta?.description || `${Math.ceil(duration / 60)} min · uniquement à partir du transcript vérifié`}</p>
      {playing && current && <p className="podcast-now"><strong>{current.host === "host_a" ? "Thomas" : "Camille"}</strong> — {current.text}</p>}
      <div className="podcast-progress"><span style={{ width: `${turns.length ? ((active + 1) / turns.length) * 100 : 0}%` }}/></div>
      {meetingId && <div className="podcast-studio">
        <div className="podcast-formats">{Object.entries(FORMATS).map(([key, label]) => <button className={format === key ? "active" : ""} onClick={() => setFormat(key)} key={key}>{label}</button>)}</div>
        <label>Durée <select value={minutes} onChange={(event) => setMinutes(Number(event.target.value))}><option value="2">2 min</option><option value="5">5 min</option><option value="10">10 min</option></select></label>
        <input value={focus} onChange={(event) => setFocus(event.target.value)} maxLength="300" placeholder="Angle facultatif : décisions, risques, projet…"/>
        <button className="podcast-generate" onClick={generate} disabled={busy}>{busy ? "Création…" : "Créer ce brief"}</button>
      </div>}
      {error && <span className="podcast-error">{error}</span>}
    </div>
    <button className={`podcast-button ${playing ? "playing" : ""}`} onClick={playing ? stop : play} disabled={!supported || !turns.length}>
      {playing ? "Arrêter" : "Écouter"}
    </button>
  </article>;
}
