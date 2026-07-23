# Cadre de protection des données de Scribe

Version : 2026-07-22

## Finalités et données minimales

Scribe traite les données uniquement pour authentifier l’utilisateur, recueillir le
consentement individuel, transcrire une réunion et produire son compte rendu.

- Compte : nom, e-mail, mot de passe hashé, versions des accords.
- Invitation : nom, e-mail, preuve horodatée du consentement et du retrait.
- Réunion : audio, transcription diarisée, décisions, actions et compte rendu.
- Technique : état du traitement et erreurs nécessaires au diagnostic.

Les e-mails des participants ne sont jamais envoyés au modèle d’IA. Les liens de
consentement sont stockés sous forme de hash et non en clair.

## Cycle de vie

1. Chaque participant reçoit une information avant la réunion.
2. Le dictaphone reste bloqué jusqu’à l’accord actif de tous les participants.
3. L’organisateur annonce à nouveau Scribe aux personnes présentes.
4. Tout retrait arrête la session et le navigateur contrôle l’état toutes les trois secondes.
5. L’audio est supprimé après la tentative de traitement, réussie ou non.
6. Les transcriptions et comptes rendus expirent après 30 jours.
7. L’utilisateur peut exporter ses données ou supprimer son compte.
8. Un participant peut retirer son accord ou demander l’effacement depuis son lien.

## Sous-traitance

Mistral AI reçoit l’audio pour Voxtral et la transcription pour Mistral Medium 3.5.
Le DPA Mistral et le DPA client doivent être signés et archivés avant la production.
L’identité du responsable de traitement, ses coordonnées, le contact données
personnelles et la localisation contractuelle doivent également être finalisés.

## Limites juridiques

Le code facilite la conformité mais ne peut pas certifier à lui seul une conformité
RGPD à 100 %. La base légale, les durées, le registre des traitements, l’AIPD éventuelle,
les contrats, les habilitations et la réponse aux demandes doivent être validés par le
responsable de traitement ou son conseil.
