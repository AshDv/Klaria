# Klaria

Klaria rejoint une réunion Google Meet ou Microsoft Teams, produit une transcription
attribuée aux intervenants et transforme l’échange en compte rendu, décisions, actions,
questions, risques et brief audio à deux voix. Le dictaphone présentiel reste disponible.

## Fonctionnalités

- compte local et Google SSO avec OAuth 2.0 et OpenID Connect ;
- consentement individuel envoyé par e-mail avant toute capture ;
- bot visible dans Google Meet et Microsoft Teams ;
- transcription en direct avec attribution des intervenants ;
- WebSocket temps réel avec repli automatique sur la synchronisation REST ;
- saisie des participants avant l’envoi de leurs demandes de consentement ;
- commande `STOP KLARIA` dans le chat avec arrêt et effacement immédiats ;
- Mistral Medium 3.5 avec sortie JSON validée et preuves par segment ;
- mentions directes avec auteur, contexte et passages justificatifs ;
- distinction entre décisions confirmées, proposées et reportées ;
- plan d’action avec responsable, échéance et priorité uniquement quand ils sont explicites ;
- dashboard, bibliothèque, vue décisions, vue actions et transcription ;
- brief audio à deux voix généré localement par le navigateur ;
- arrêt et purge si un participant retire son consentement ;
- publication du récapitulatif et du lien Klaria dans le chat avant le départ du bot ;
- export, suppression du compte et expiration des résultats.

## Stack

- Frontend : React 18, JavaScript, CSS et Vite.
- Backend : Python 3.12, FastAPI, SQLModel et Pydantic.
- Base : SQLite en local, PostgreSQL managé en ligne.
- Bot en ligne : Vexa pour Meet et Teams, sans enregistrement audio activé.
- IA : Voxtral pour le dictaphone et `mistral-medium-3-5` pour l’analyse structurée.
- Hébergement : Netlify pour le frontend, conteneur serverless pour l’API.

Voir [l’architecture Sprint 2](docs/S2_ARCHITECTURE.md) et le
[guide de mise en ligne](docs/DEPLOYMENT.md).

## Lancement local

Copier `server/.env.example` vers `server/.env`, renseigner les services utilisés, puis :

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

- Interface : `http://localhost:5174`
- API : `http://localhost:8000`
- Documentation API : `http://localhost:8000/docs`

Pour activer le bot en ligne, `VEXA_API_KEY` est obligatoire. Sans SMTP, Klaria ne
crée pas de session de consentement et n’envoie donc aucun bot.

Pour Teams, Vexa exige l’identifiant numérique et le code secret présents dans
l’invitation lorsque le lien collé n’est pas déjà au format `teams.live.com/meet/...`.

## Contrôles

```powershell
server\.venv\Scripts\ruff.exe check server\app server\tests
server\.venv\Scripts\python.exe -m pytest -q

Set-Location web
npm run build
```

Le code fournit des mesures techniques de protection des données. Les informations
légales, contrats, durées et sous-traitants doivent être validés avant une production réelle.
