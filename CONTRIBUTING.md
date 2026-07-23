# Contribuer à Scribe

Le dépôt final est `https://github.com/AshDv/ScribeProject`. Le dossier local actuel
provient d’un ancien dépôt et sert uniquement de source de travail. Il ne doit pas être
poussé directement vers le dépôt final avec son historique.

Le plan complet des tickets, branches, commits, dépendances, reviewers et preuves RNCP
se trouve dans `docs/S1_EXECUTION_PLAN.md`.

## Règles non négociables

- Une fonctionnalité correspond à un ticket Jira et une branche Git.
- La personne assignée réalise, comprend, teste et committe réellement son ticket.
- Il est interdit d’utiliser `--author`, d’antidater ou de fabriquer l’activité d’un membre.
- Un commit doit représenter une seule intention et laisser le projet dans un état cohérent.
- Aucun `.env`, secret, audio, fichier de données personnelles ou base locale ne va dans Git.
- Une pull request référence le ticket, présente les tests et est relue par un autre membre.
- Une PR rouge, non relue ou avec une conversation ouverte ne peut pas être fusionnée.
- Les commits sont conservés avec `Create a merge commit`; aucun squash de tout le ticket.

## Avant chaque ticket

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c feature/s1-XX-description
```

## Avant chaque commit

```powershell
git status --short
git diff --check
git add chemin\exact\du\fichier
git diff --cached
git commit -m "type(scope): intention précise"
```

Ne jamais utiliser `git add *`. Le développeur pousse ensuite sa branche et ouvre une PR
vers `develop` :

```powershell
git push -u origin feature/s1-XX-description
```

## Contrôles obligatoires

```powershell
server\.venv\Scripts\ruff.exe check server\app server\tests
server\.venv\Scripts\python.exe -m pytest -q

Set-Location web
npm run build
```

## Definition of Done

- critères d’acceptation Jira cochés avec une preuve réelle ;
- tests utiles verts localement et dans GitHub Actions ;
- aucun secret ou fichier personnel dans le diff ;
- branche à jour avec `develop` ;
- PR liée au ticket et relue par la personne prévue ;
- capture pour une interface ou résultat de test pour une API ;
- capacité de l’auteur à expliquer son code pendant la soutenance.
