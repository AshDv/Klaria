# Livraison équipe — Sprint 2

Ce guide transfère le Sprint 2 vers `AshDv/NolyaProject` sans copier de secret et sans mélanger les contributions. Une branche est créée, relue et fusionnée avant de passer à la suivante.

## Règles communes

- Décompresser `nolya-s2-delivery-final.zip` dans `Downloads/nolya-s2-delivery-final`.
- Travailler dans un clone propre de `https://github.com/AshDv/NolyaProject.git`.
- Ne jamais copier `server/.env`, `nolya.db`, `node_modules` ou `.venv`.
- Relire les fichiers et lancer les tests avant de valider un commit.
- Une autre personne relit la PR. La branche est fusionnée dans `develop`, puis la personne suivante commence.
- Utiliser une fusion normale, sans modifier les auteurs des commits.

## Préparation Windows

```powershell
cd "$HOME\Downloads"
git clone https://github.com/AshDv/NolyaProject.git NolyaProject-s2
cd .\NolyaProject-s2
git switch develop
git pull --ff-only origin develop
$Source = "$HOME\Downloads\nolya-s2-delivery-final"
```

## Préparation macOS

```bash
cd ~/Downloads
git clone https://github.com/AshDv/NolyaProject.git NolyaProject-s2
cd NolyaProject-s2
git switch develop
git pull --ff-only origin develop
SOURCE="$HOME/Downloads/nolya-s2-delivery-final"
```

Pour chaque étape : remplacer uniquement les fichiers annoncés, vérifier le diff, faire les commits indiqués, pousser la branche, puis ouvrir la PR vers `develop`.

## Ordre des branches

### 1. Mehdi — domaine des réunions distantes

Branche : `feature/s2-remote-domain`

Fichiers :

- `server/app/models.py`
- `server/app/config.py`
- `server/app/db.py`
- `server/.env.example`

Commits :

```text
feat(meetings): add remote meeting data model
feat(config): configure meeting providers
fix(database): migrate structured reports
```

### 2. Yanis — intelligence de réunion

Branche : `feature/s2-meeting-intelligence`

Fichiers :

- `server/app/meeting_skills.py`
- `server/app/llm.py`
- `server/app/processing.py`
- `server/app/routes.py`
- `server/tests/test_processing.py`

Commits :

```text
feat(summary): structure meeting intelligence
feat(reports): store podcast scripts
test(summary): verify structured reports
```

### 3. Ashwin — connexion du bot

Branche : `feature/s2-vexa-client`

Fichier : `server/app/vexa.py`

Commit :

```text
feat(bot): connect Meet and Teams meetings
```

### 4. Ashwin — cycle de vie de la réunion

Branche : `feature/s2-remote-lifecycle`

Fichiers :

- `server/app/remote_processing.py`
- `server/app/poller.py`

Commits :

```text
feat(meetings): process live meeting transcripts
fix(poller): expose remote processing helpers
```

### 5. Aymen — consentement et confidentialité

Branche : `feature/s2-remote-consent`

Fichiers :

- `server/app/consent_routes.py`
- `server/app/emailing.py`
- `server/app/legal_routes.py`
- `server/app/retention.py`
- `docs/PRIVACY.md`

Commits :

```text
feat(consent): stop bots after withdrawal
feat(privacy): erase remote meeting data
docs(privacy): document meeting processors
```

### 6. Mehdi — API et conteneur backend

Branche : `feature/s2-remote-api`

Fichiers :

- `server/app/remote_routes.py`
- `server/app/main.py`
- `server/tests/test_remote_meetings.py`
- `server/requirements.txt`
- `server/Dockerfile`
- `server/.dockerignore`

Commits :

```text
feat(api): expose remote meeting endpoints
test(meetings): verify consent to report flow
build(api): add production container
```

### 7. Aymen — création d'une réunion distante

Branche : `feature/s2-remote-launcher`

Fichiers :

- `web/src/api.js`
- `web/src/RemoteMeetingWorkflow.jsx`

Commits :

```text
feat(web): connect remote meeting API
feat(web): add meeting launch workflow
```

### 8. Ashwin — salle de réunion en direct

Branche : `feature/s2-live-room`

Fichier : `web/src/RemoteMeetingView.jsx`

Commit :

```text
feat(web): display live diarized transcript
```

### 9. Yanis — briefing audio

Branche : `feature/s2-audio-brief`

Fichier : `web/src/PodcastPlayer.jsx`

Commit :

```text
feat(web): play two-voice meeting brief
```

### 10. Mehdi — tableau de bord et livraison

Branche : `feature/s2-dashboard-release`

Fichiers :

- `web/src/Dashboard.jsx`
- `web/src/App.jsx`
- `web/src/index.css`
- `web/.env.example`
- `netlify.toml`
- `README.md`
- `docs/S2_ARCHITECTURE.md`
- `docs/DEPLOYMENT.md`

Commits :

```text
feat(web): add meeting dashboard
style(web): apply responsive product design
docs(release): document deployment
```

## Commandes d'une étape sous Windows

Exemple à adapter avec la branche et les fichiers de l'étape :

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c feature/s2-example
Copy-Item "$Source\server\app\example.py" ".\server\app\example.py" -Force
git add server/app/example.py
git diff --cached --check
git diff --cached
git commit -m "feat(example): add example"
git push -u origin feature/s2-example
gh pr create --base develop --head feature/s2-example --title "S2: add example" --body "Ajoute la fonctionnalité et ses vérifications."
```

## Commandes d'une étape sous macOS

```bash
git switch develop
git pull --ff-only origin develop
git switch -c feature/s2-example
cp "$SOURCE/server/app/example.py" ./server/app/example.py
git add server/app/example.py
git diff --cached --check
git diff --cached
git commit -m "feat(example): add example"
git push -u origin feature/s2-example
gh pr create --base develop --head feature/s2-example --title "S2: add example" --body "Ajoute la fonctionnalité et ses vérifications."
```

## Vérification finale

Après la dixième fusion :

```powershell
git switch develop
git pull --ff-only origin develop
python -m ruff check server
python -m pytest server/tests -q
cd web
npm ci
npm run build
```

Le responsable de la livraison ouvre ensuite une PR `develop` vers `main`. Cette PR n'est fusionnée que si les tests backend et le build frontend réussissent.
