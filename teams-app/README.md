# Application Teams Nolya

Le paquet `Nolya-Teams.zip` ajoute trois onglets personnels à Microsoft Teams :

- Accueil : synthèse du travail récent ;
- Réunions : événements à venir et comptes rendus ;
- Actions : engagements extraits des réunions.

Exécuter `build-package.ps1` pour reconstruire les icônes et le ZIP. Le ZIP
contient uniquement `manifest.json`, `color.png` et `outline.png`, conformément
au format Teams. Le code et les données restent hébergés sur le domaine HTTPS de
Nolya.

Pour tester, ouvrir **Applications** dans Teams, choisir **Gérer vos
applications**, puis **Charger une application personnalisée**. La publication
à toute une organisation demande ensuite l’accord de son administrateur Teams.
