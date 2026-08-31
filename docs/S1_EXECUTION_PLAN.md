# Plan d’exécution Jira, GitHub et RNCP — S1

Date de préparation : 22 juillet 2026
Échéance Jira : 26 juillet 2026
Dépôt final : `https://github.com/AshDv/KlariaProject`

## 1. Situation de départ

Le dépôt final contient uniquement un commit initial créé par Ashwin. Le dossier
`C:\Users\pc\Downloads\klaria-saas` pointe encore vers
`YanisZedira/klaria_saas` et contient un historique ancien ainsi que des changements
non commités.

Il ne faut donc ni changer son remote puis pousser, ni committer tout le dossier en une
fois. Un nouveau clone du dépôt final doit être créé dans un autre dossier. L’ancien
dossier reste une référence permettant à chaque membre de reprendre uniquement les
éléments de son ticket.

Chaque auteur doit relire, adapter et tester le code qu’il reprend. Copier aveuglément
un résultat puis modifier l’auteur Git ne constitue pas une contribution réelle.

## 2. Initialisation par Ashwin, propriétaire du dépôt

```powershell
Set-Location C:\Users\pc\Downloads
git clone https://github.com/AshDv/KlariaProject.git KlariaProject
Set-Location KlariaProject
git switch -c develop
git push -u origin develop
```

Dans GitHub, protéger `main` et `develop` avec les règles suivantes :

- pull request obligatoire ;
- au moins une approbation ;
- conversations résolues ;
- checks `backend` et `frontend` obligatoires dès que la CI existe ;
- force push et suppression interdits ;
- `main` reçoit uniquement les releases validées depuis `develop`.

Chaque membre clone ensuite ce nouveau dépôt avec son propre compte et configure sa
véritable identité :

```powershell
git config user.name "Prénom Nom"
git config user.email "adresse-liée-au-compte-github"
git config --get user.name
git config --get user.email
```

Ne jamais utiliser `git commit --author`, ne jamais modifier les dates de commit et ne
jamais partager un même compte GitHub.

## 3. Les 13 tickets et leurs propriétaires

| Ordre | Ticket | Branche | Responsable | Reviewer | Points | Dépend de |
|---:|---|---|---|---|---:|---|
| 1 | S1-01 Set up the clean project foundation | `feature/s1-01-project-foundation` | Yanis | Ashwin | 2 | aucune |
| 2 | S1-02 Create the core data model | `feature/s1-02-core-data-model` | Ashwin | Aymen | 3 | S1-01 |
| 3 | S1-03 Build secure authentication and Google SSO | `feature/s1-03-authentication-backend` | Aymen | Yanis | 3 | S1-02 |
| 4 | S1-04 Create the authentication interface | `feature/s1-04-authentication-interface` | Mehdi | Aymen | 3 | S1-03 |
| 5 | S1-05 Add legal onboarding and privacy rights | `feature/s1-05-privacy-backend` | Aymen | Mehdi | 3 | S1-03 |
| 6 | S1-06 Create participant consent invitations | `feature/s1-06-consent-backend` | Aymen | Ashwin | 5 | S1-02, S1-05 |
| 7 | S1-07 Create the consent and privacy interface | `feature/s1-07-consent-interface` | Mehdi | Yanis | 5 | S1-04, S1-06 |
| 8 | S1-08 Create the secure recording API | `feature/s1-08-recording-api` | Yanis | Aymen | 3 | S1-03, S1-06 |
| 9 | S1-09 Create the consent-aware browser dictaphone | `feature/s1-09-browser-dictaphone` | Yanis | Mehdi | 5 | S1-07, S1-08 |
| 10 | S1-10 Transcribe and diarize audio with Voxtral | `feature/s1-10-voxtral-diarization` | Ashwin | Yanis | 5 | S1-08 |
| 11 | S1-11 Generate the structured Mistral meeting report | `feature/s1-11-mistral-report` | Ashwin | Mehdi | 5 | S1-10 |
| 12 | S1-12 Create the meeting results interface | `feature/s1-12-results-interface` | Mehdi | Ashwin | 5 | S1-04, S1-11 |
| 13 | S1-13 Validate and release the complete S1 journey | `test/s1-13-release-validation` | Yanis | Toute l’équipe | 3 | S1-01 à S1-12 |

Charge : Yanis 13 points, Aymen 11, Ashwin 13 et Mehdi 13.

## 4. Ordre des pull requests

1. Yanis fusionne S1-01.
2. Ashwin repart du `develop` mis à jour et fusionne S1-02.
3. Aymen fusionne S1-03.
4. Mehdi peut réaliser S1-04 pendant qu’Aymen réalise S1-05.
5. Aymen réalise S1-06 après la fusion de S1-05.
6. Mehdi réalise S1-07 pendant que Yanis réalise S1-08.
7. Yanis réalise S1-09 pendant qu’Ashwin réalise S1-10.
8. Ashwin réalise S1-11.
9. Mehdi réalise S1-12.
10. Yanis ouvre S1-13, toute l’équipe la valide, puis une PR `develop` vers `main`
    produit la release `s1-v1.0.0`.

Une branche parallèle doit être resynchronisée avant la PR :

```powershell
git fetch origin
git merge origin/develop
```

En cas de conflit, l’auteur du ticket le résout et rejoue les tests. Aucun `push --force`
ou `push --force-with-lease` n’est utilisé dans ce projet.

## 5. Commits exacts par ticket

### S1-01 — Yanis

1. `chore(project): add FastAPI and React foundations`
2. `chore(config): add safe local configuration`
3. `test(quality): configure project checks`

### S1-02 — Ashwin

1. `feat(data): add users and versioned agreements`
2. `feat(data): add consent sessions and participant proofs`
3. `feat(data): add recordings and structured reports`

### S1-03 — Aymen

1. `feat(auth): add password registration and login`
2. `feat(auth): protect private resources with JWT`
3. `feat(auth): add Google OAuth and OIDC login`
4. `test(auth): cover authentication boundaries`

### S1-04 — Mehdi

1. `feat(ui): add the responsive Klaria shell`
2. `feat(auth-ui): add account forms`
3. `feat(auth-ui): add SSO callback and private navigation`

### S1-05 — Aymen

1. `feat(privacy): expose notices and versioned agreements`
2. `feat(privacy): add export and account erasure`
3. `feat(retention): purge expired meeting data`
4. `test(privacy): cover notices and erasure`

### S1-06 — Aymen

1. `feat(consent): add participant consent sessions`
2. `feat(email): send hashed consent links over SMTP`
3. `feat(consent): block and stop unauthorized recording`
4. `test(consent): cover accept refuse withdraw and erase`

### S1-07 — Mehdi

1. `feat(consent-ui): add participant setup`
2. `feat(consent-ui): add the public consent page`
3. `feat(consent-ui): show live consent status and room notice`
4. `feat(privacy-ui): add legal and account controls`

### S1-08 — Yanis

1. `feat(recording): add owner-scoped audio upload`
2. `feat(recording): add processing states and deletion`
3. `test(recording): cover validation and ownership`

### S1-09 — Yanis

1. `feat(recorder): capture and preview browser audio`
2. `feat(recorder): add pause resume and duration`
3. `feat(recorder): discard audio after consent withdrawal`

### S1-10 — Ashwin

1. `feat(stt): add the Voxtral transcription client`
2. `feat(stt): enable diarization and segment timestamps`
3. `feat(stt): persist ordered speaker segments`
4. `test(stt): cover segment normalization and failures`

### S1-11 — Ashwin

1. `feat(summary): define the structured report schema`
2. `feat(summary): add the evidence-linked Medium 3.5 prompt`
3. `feat(summary): persist decisions actions risks and coverage`
4. `perf(summary): remove duplicate tokens and retry rate limits`
5. `test(summary): require exact segment coverage`

### S1-12 — Mehdi

1. `feat(results-ui): add meeting history and statuses`
2. `feat(results-ui): show diarized transcript`
3. `feat(results-ui): show the structured report`
4. `feat(results-ui): handle empty loading and failure states`

### S1-13 — Yanis, revue par toute l’équipe

1. `test(e2e): cover the complete consent-to-report journey`
2. `ci(project): run backend and frontend checks on pull requests`
3. `docs(rncp): add architecture privacy and evidence matrix`
4. `chore(release): prepare the S1 demo`

Ces intitulés sont un plan, pas une permission de créer des commits vides. Si un commit
ne correspond pas à un changement réel, il n’est pas créé.

## 6. Procédure identique pour chaque ticket

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c feature/s1-XX-description
```

Le responsable reprend uniquement les éléments de son ticket depuis l’ancien dossier,
les adapte au nouveau dépôt et exécute le test prévu. Pour chaque brique :

```powershell
git status --short
git diff --check
git add chemin\exact\du\fichier
git diff --cached
git commit -m "message prévu"
```

Une fois le ticket terminé :

```powershell
server\.venv\Scripts\ruff.exe check server\app server\tests
server\.venv\Scripts\python.exe -m pytest -q
Set-Location web
npm run build
Set-Location ..
git push -u origin feature/s1-XX-description
```

## 7. Contenu obligatoire d’une pull request

```markdown
## Ticket
S1-XX — lien Jira

## Pourquoi
Besoin utilisateur traité en une phrase.

## Changements
- changement 1
- changement 2

## Validation
- [ ] Critères Jira vérifiés
- [ ] Tests backend réussis
- [ ] Build frontend réussi
- [ ] Aucun secret ou donnée personnelle dans le diff

## Preuves
Commande et résultat, capture ou courte vidéo.

## Risques et limites
Ce qui reste volontairement hors du ticket.
```

Le reviewer vérifie le code, reproduit au moins le test principal et laisse soit une
approbation, soit une demande de modification précise. Un simple « OK » sans lecture
n’est pas une preuve de revue.

## 8. Preuves à conserver pour le RNCP

Pour chaque ticket :

- lien Jira et critères cochés ;
- branche et commits de l’auteur réel ;
- pull request et discussion de revue ;
- sortie de test ou capture fonctionnelle ;
- éventuel bug découvert et commit correctif ;
- courte note expliquant le choix technique et sa limite.

Ces éléments couvrent la spécification et l’architecture du BC01, le cycle itératif et
les validations du BC02, ainsi que le développement, la sécurité et l’optimisation du
BC03. Le référentiel exige des preuves de conception, de gestion itérative, de tests,
de qualité et de correction ; il n’exige pas un grand nombre artificiel de commits.

## 9. Release finale

Après validation de S1-13 :

```powershell
git switch develop
git pull --ff-only origin develop
```

Ouvrir une PR `develop` vers `main`, obtenir l’approbation de toute l’équipe, puis créer
la release GitHub et le tag `s1-v1.0.0`. La démonstration doit utiliser exactement ce tag,
pas une branche locale non poussée.
