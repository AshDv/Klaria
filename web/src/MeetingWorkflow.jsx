import { useEffect, useRef, useState } from "react";
import { api } from "./api";

const formatTime = (seconds) =>
  `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

export function MeetingWorkflow({ onCreated }) {
  const [meeting, setMeeting] = useState(null);

  if (!meeting) return <MeetingSetup onCreated={setMeeting} />;
  if (meeting.status !== "recording") {
    return <ConsentStatus meeting={meeting} onChange={setMeeting} />;
  }
  return <Recorder meeting={meeting} onCreated={onCreated} />;
}

function MeetingSetup({ onCreated }) {
  const [title, setTitle] = useState("Nouvelle réunion");
  const [participants, setParticipants] = useState([{ name: "", email: "" }]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const update = (index, field, value) => {
    setParticipants((items) =>
      items.map((item, position) =>
        position === index ? { ...item, [field]: value } : item,
      ),
    );
  };

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onCreated(await api.createConsentSession({ title, participants }));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="page">
    <header className="page-header"><div><span className="eyebrow">Consentement préalable</span><h1>Préparer la réunion</h1><p>Chaque participant doit accepter par e-mail avant l’enregistrement.</p></div></header>
    <form className="content-card meeting-form" onSubmit={create}>
      <label className="field"><span>Titre de la réunion</span><input value={title} onChange={(event) => setTitle(event.target.value)} required /></label>
      <div className="participant-heading"><h3>Participants</h3><button type="button" className="text-button inline" onClick={() => setParticipants([...participants, { name: "", email: "" }])}>+ Ajouter</button></div>
      {participants.map((participant, index) => <div className="participant-fields" key={index}>
        <input aria-label={`Nom du participant ${index + 1}`} placeholder="Nom complet" value={participant.name} onChange={(event) => update(index, "name", event.target.value)} required />
        <input aria-label={`E-mail du participant ${index + 1}`} type="email" placeholder="E-mail" value={participant.email} onChange={(event) => update(index, "email", event.target.value)} required />
        {participants.length > 1 && <button type="button" className="icon-button danger" aria-label={`Retirer le participant ${index + 1}`} onClick={() => setParticipants(participants.filter((_, position) => position !== index))}>×</button>}
      </div>)}
      <p className="privacy-hint">Ajoutez toutes les personnes dont la voix peut être captée, vous compris. Scribe utilise ces adresses uniquement pour envoyer et prouver le consentement.</p>
      {error && <div className="alert error">{error}</div>}
      <button className="primary-button compact" disabled={busy}>{busy ? "Envoi…" : "Envoyer les demandes de consentement"}</button>
    </form>
  </section>;
}

function ConsentStatus({ meeting, onChange }) {
  const [notice, setNotice] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const refresh = async () => onChange(await api.getConsentSession(meeting.id));
    const timer = setInterval(() => refresh().catch(() => {}), 3000);
    return () => clearInterval(timer);
  }, [meeting.id, onChange]);

  async function start() {
    if (!notice) {
      setError("Annoncez la présence de Scribe aux personnes dans la salle.");
      return;
    }
    try {
      onChange(await api.startConsentSession(meeting.id));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  return <section className="page">
    <header className="page-header"><div><span className="eyebrow">Accords des participants</span><h1>{meeting.title}</h1><p>L’enregistrement reste bloqué tant que tous les accords ne sont pas actifs.</p></div></header>
    <div className="content-card consent-dashboard">
      {meeting.participants.map((participant) => <div className="consent-row" key={participant.id}>
        <div><strong>{participant.name}</strong><small>{participant.email}</small></div>
        <span className={`status ${participant.consented_at && !participant.withdrawn_at ? "completed" : "uploaded"}`}>{participant.withdrawn_at ? "Retiré" : participant.consented_at ? "Accepté" : "En attente"}</span>
      </div>)}
      <label className="consent"><input type="checkbox" checked={notice} onChange={(event) => setNotice(event.target.checked)} /><span><strong>J’annonce Scribe à toutes les personnes présentes</strong><small>Je leur rappelle que l’enregistrement peut être arrêté immédiatement.</small></span></label>
      {error && <div className="alert error">{error}</div>}
      <button className="primary-button compact" disabled={!meeting.all_consented} onClick={start}>Ouvrir le dictaphone</button>
    </div>
  </section>;
}

function Recorder({ meeting, onCreated }) {
  const [state, setState] = useState("idle");
  const [seconds, setSeconds] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [error, setError] = useState("");
  const recorder = useRef(null);
  const stream = useRef(null);
  const chunks = useRef([]);
  const consentRevoked = useRef(false);

  useEffect(() => {
    if (state !== "recording") return undefined;
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [state]);

  useEffect(() => {
    if (!['recording', 'paused'].includes(state)) return undefined;
    const verify = async () => {
      const current = await api.getConsentSession(meeting.id);
      if (current.status !== "recording" || !current.all_consented) {
        consentRevoked.current = true;
        if (recorder.current?.state !== "inactive") recorder.current?.stop();
        setAudioBlob(null);
        setAudioUrl((currentUrl) => {
          if (currentUrl) URL.revokeObjectURL(currentUrl);
          return "";
        });
        setError("Enregistrement arrêté : un participant a retiré son accord.");
      }
    };
    const timer = setInterval(() => verify().catch(() => {}), 3000);
    return () => clearInterval(timer);
  }, [meeting.id, state]);

  useEffect(() => () => {
    stream.current?.getTracks().forEach((track) => track.stop());
    if (audioUrl) URL.revokeObjectURL(audioUrl);
  }, [audioUrl]);

  async function start() {
    setError("");
    try {
      consentRevoked.current = false;
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks.current = [];
      recorder.current = new MediaRecorder(stream.current);
      recorder.current.ondataavailable = (event) => {
        if (event.data.size) chunks.current.push(event.data);
      };
      recorder.current.onstop = () => {
        if (consentRevoked.current) {
          chunks.current = [];
          setAudioBlob(null);
          setState("idle");
          stream.current?.getTracks().forEach((track) => track.stop());
          return;
        }
        const blob = new Blob(chunks.current, { type: recorder.current.mimeType || "audio/webm" });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        setState("ready");
        stream.current?.getTracks().forEach((track) => track.stop());
      };
      recorder.current.start();
      setSeconds(0);
      setState("recording");
    } catch {
      setError("Microphone indisponible. Vérifiez l’autorisation du navigateur.");
    }
  }

  function pause() {
    if (recorder.current?.state === "recording") {
      recorder.current.pause();
      setState("paused");
    } else {
      recorder.current?.resume();
      setState("recording");
    }
  }

  function stop() {
    if (recorder.current && recorder.current.state !== "inactive") recorder.current.stop();
  }

  function reset() {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioBlob(null);
    setAudioUrl("");
    setSeconds(0);
    setState("idle");
    setError("");
  }

  async function send() {
    setState("uploading");
    try {
      const item = await api.createRecording(meeting.title, audioBlob, true, meeting.id);
      onCreated(item.id);
    } catch (requestError) {
      setError(requestError.message);
      setState("ready");
    }
  }

  return <section className="page">
    <header className="page-header"><div><span className="eyebrow">Enregistrement autorisé</span><h1>{meeting.title}</h1><p>Au début, chaque personne dit « Je suis Prénom Nom ». Voxtral sépare ensuite les intervenants et Mistral Medium 3.5 produit le compte rendu.</p></div><span className="secure-badge">Consentements actifs</span></header>
    <div className="recorder-card">
      <div className={`orb ${state === "recording" ? "live" : ""}`}><div className="orb-inner">●</div></div>
      <div className="timer">{formatTime(seconds)}</div>
      <p className="recorder-status">{state === "recording" ? "Enregistrement en cours" : state === "paused" ? "En pause" : state === "ready" ? "Audio prêt" : "Prêt à enregistrer"}</p>
      {state === "idle" && <button className="record-button" onClick={start}><span /> Démarrer</button>}
      {['recording', 'paused'].includes(state) && <div className="control-row"><button className="secondary-button" onClick={pause}>{state === "paused" ? "Reprendre" : "Pause"}</button><button className="stop-button" onClick={stop}>Arrêter</button></div>}
      {state === "ready" && <><audio className="audio-player" controls src={audioUrl} /><div className="control-row"><button className="secondary-button" onClick={reset}>Recommencer</button><button className="primary-button compact" onClick={send}>Transcrire et résumer</button></div></>}
      {state === "uploading" && <div className="processing-line"><span className="spinner" /> Traitement sécurisé…</div>}
      {error && <div className="alert error">{error}</div>}
    </div>
  </section>;
}
