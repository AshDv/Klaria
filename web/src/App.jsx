import { useState } from "react";
import { api, setAccessToken } from "./api";

function readSsoToken() {
  const token = new URLSearchParams(location.hash.slice(1)).get("access_token");
  if (token) { setAccessToken(token); history.replaceState(null, "", location.pathname); }
  return Boolean(token);
}

export default function App() {
  const [registered, setRegistered] = useState(readSsoToken());
  const [login, setLogin] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    try {
      if (login) await api.login(email, password);
      else await api.register(name, email, password, true, true);
      setRegistered(true);
    } catch (requestError) { setError(requestError.message); }
  }

  if (registered) return <main className="public-page"><section className="content-card public-card"><h1>Bienvenue sur Scribe</h1></section></main>;
  return <main className="public-page"><section className="content-card public-card">
    <div className="brand"><span className="brand-mark">S</span><span>Scribe</span></div>
    <h1>{login ? "Connexion" : "Créer un compte"}</h1>
    <form className="auth-form" onSubmit={submit}>
      {!login && <input placeholder="Nom complet" value={name} onChange={event => setName(event.target.value)} required />}
      <input type="email" placeholder="E-mail" value={email} onChange={event => setEmail(event.target.value)} required />
      <input type="password" minLength="10" placeholder="Mot de passe" value={password} onChange={event => setPassword(event.target.value)} required />
      {!login && <><label className="legal-check"><input type="checkbox" required /> Information RGPD lue</label><label className="legal-check"><input type="checkbox" required /> CGU acceptées</label></>}
      {error && <div className="alert error">{error}</div>}
      <button className="primary-button">{login ? "Se connecter" : "Créer mon compte"}</button>
    </form>
    false && <button className="text-button" onClick={() => setLogin(!login)}>{login ? "Créer un compte" : "Se connecter"}</button>
  </section></main>;
}
