# Cadre de protection des données de Klaria

Version : 2026-08-10

## Finalités et données minimales

Klaria traite les données uniquement pour authentifier l’utilisateur, recueillir le
consentement individuel, transcrire une réunion et produire son compte rendu.

- Compte : nom, e-mail, mot de passe hashé, versions des accords.
- Invitation : nom, e-mail, preuve horodatée du consentement et du retrait.
- Réunion : transcription diarisée, décisions, actions et compte rendu.
- Calendrier Teams : noms et e-mails des invités importés pour demander leur accord.
- Technique : état du traitement et erreurs nécessaires au diagnostic.

Les e-mails des participants ne sont jamais envoyés au modèle d’IA. Les liens de
consentement sont stockés sous forme de hash et non en clair.

## Cycle de vie

1. Chaque participant reçoit une information avant la réunion.
2. Le dictaphone et le bot restent bloqués jusqu’à l’accord actif de tous les participants.
3. L’organisateur annonce à nouveau Klaria aux personnes présentes.
4. Tout retrait arrête la capture et déclenche l’effacement des données temporaires du bot.
5. La commande « STOP KLARIA » dans le chat produit le même arrêt immédiat.
6. L’audio est supprimé après la tentative de traitement, réussie ou non.
7. Les transcriptions et comptes rendus expirent après 30 jours.
8. L’utilisateur peut exporter ses données ou supprimer son compte.
9. Un participant peut retirer son accord ou demander l’effacement depuis son lien.

## Sous-traitance

Mistral AI reçoit l’audio pour Voxtral et la transcription pour Mistral Medium 3.5.
Vexa reçoit le flux des réunions en ligne pour produire la transcription en direct.
L’enregistrement audio Vexa est désactivé et la réunion temporaire est purgée après analyse.
Le bot consulte le chat uniquement pour détecter une demande d'arrêt et publier le
récapitulatif. Klaria ne stocke pas les messages du chat. Les participants sont renseignés
par l’organisateur uniquement pour recueillir leur consentement avant la capture.
Le DPA Mistral et le DPA client doivent être signés et archivés avant la production.
L’identité du responsable de traitement, ses coordonnées, le contact données
personnelles et la localisation contractuelle doivent également être finalisés.

## Limites juridiques

Le code facilite la conformité mais ne peut pas certifier à lui seul une conformité
RGPD à 100 %. La base légale, les durées, le registre des traitements, l’AIPD éventuelle,
les contrats, les habilitations et la réponse aux demandes doivent être validés par le
responsable de traitement ou son conseil.
