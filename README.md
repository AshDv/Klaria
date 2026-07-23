# Scribe - MVP de compte rendu consenti

Scribe enregistre une réunion uniquement après l’accord individuel de chaque
participant. Voxtral réalise la transcription diarisée, puis Mistral Medium 3.5
produit un compte rendu structuré et traçable.

## Fonctionnalités

- compte local et Google SSO avec OAuth 2.0 et OpenID Connect ;
- acceptation séparée des CGU et de l’information RGPD ;
- invitations de consentement envoyées par e-mail ;
- démarrage bloqué jusqu’à l’accord actif de tous les participants ;
- seconde annonce obligatoire aux personnes présentes ;
- retrait en ligne qui arrête la session ;
- dictaphone avec pause, reprise et écoute ;
- transcription Voxtral avec diarisation et horodatage ;
- Mistral Medium 3.5 avec sortie JSON validée ;
- résumé, compte rendu, intervenants, décisions, actions, questions et risques ;
- traçabilité de chaque segment traité ;
- suppression de l’audio après traitement ;
- export et suppression des données ;
- purge des résultats après 30 jours.

## Technologies

- Frontend : React 18, JavaScript, CSS et Vite.
- Backend : Python 3.12, FastAPI, SQLModel et Pydantic.
- Authentification : bcrypt, JWT, Authlib, OAuth 2.0 et OpenID Connect.
- IA : `voxtral-mini-latest` et `mistral-medium-3-5`.
- Développement : SQLite. La production nécessite une base et un stockage managés.

## Lancement Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Application : `http://localhost:5174`

## Configuration obligatoire

Copier `server/.env.example` vers `server/.env`, puis renseigner :

```dotenv
MISTRAL_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
DATA_CONTROLLER_NAME=
DATA_CONTROLLER_ADDRESS=
PRIVACY_CONTACT_EMAIL=
```

Sans SMTP, Scribe refuse de créer une réunion : aucun faux e-mail et aucun
contournement du consentement ne sont utilisés.

## Qualité

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check app tests

cd ..\web
npm run build
```

## Conformité et RNCP

- [Cadre de protection des données](docs/PRIVACY.md)
- [Traçabilité RNCP36146](docs/RNCP_TRACEABILITY.md)
- [Workflow Git de l’équipe](CONTRIBUTING.md)

Le logiciel fournit des mesures techniques de conformité. La conformité juridique
finale exige encore l’identité réelle du responsable de traitement, le contact
protection des données, le registre, les durées validées et les DPA Mistral/client.
