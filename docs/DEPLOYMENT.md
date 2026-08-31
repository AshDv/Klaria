# Mise en ligne

## 1. Base PostgreSQL

Créer une base PostgreSQL managée dans la même région que l’API. Copier sa chaîne de
connexion TLS dans la variable secrète `DATABASE_URL` :

```text
postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
```

## 2. Backend serverless

L’image est définie par `server/Dockerfile` et écoute automatiquement la variable `PORT`.

```powershell
docker build -t rg.fr-par.scw.cloud/VOTRE_NAMESPACE/nolya-api:latest .\server
docker push rg.fr-par.scw.cloud/VOTRE_NAMESPACE/nolya-api:latest
```

Dans Scaleway Serverless Containers, déployer cette image, choisir le port exposé par
`PORT`, rendre seulement l’endpoint HTTPS public et configurer au minimum :

```dotenv
ENVIRONMENT=production
DATABASE_URL=
SECRET_KEY=
CORS_ORIGINS=https://VOTRE_SITE.netlify.app
FRONTEND_URL=https://VOTRE_SITE.netlify.app
API_PUBLIC_URL=https://VOTRE_API
MISTRAL_API_KEY=
MISTRAL_BASE_URL=https://api.eu.mistral.ai/v1
VEXA_API_KEY=
VEXA_API_URL=https://VOTRE_INSTANCE_VEXA
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

Les valeurs sensibles sont ajoutées dans l’interface du fournisseur, jamais dans Git.
Tester ensuite `https://VOTRE_API/api/health`.

## 3. Frontend Netlify

Depuis la racine du dépôt :

```powershell
npm install -g netlify-cli
netlify login
netlify init
netlify env:set VITE_API_URL https://VOTRE_API
netlify deploy --build --prod
```

`netlify.toml` utilise `web` comme dossier de build, exécute `npm run build`, publie
`web/dist` et redirige les routes React vers `index.html`.

## 4. OAuth et CORS

Dans Google Cloud, ajouter exactement :

```text
https://VOTRE_API/api/auth/sso/google/callback
```

Reporter l’URL Netlify exacte dans `CORS_ORIGINS` et `FRONTEND_URL`, puis redéployer
l’API. Une prévisualisation Netlify utilise une autre origine et doit être ajoutée
explicitement si elle doit appeler l’API.

## 5. Validation avant ouverture

- `/api/health` confirme Mistral, Vexa, Google et SMTP ;
- une invitation arrive sur une adresse de test ;
- le bot attend les accords et apparaît sous un nom visible ;
- l’hôte admet le bot et le transcript live s’affiche ;
- `STOP NOLYA` dans le chat arrête le bot et efface le direct ;
- le récapitulatif est publié dans le chat avant le départ du bot ;
- la fin produit le rapport et confirme la purge Vexa ;
- l’export et la suppression du compte fonctionnent ;
- aucun secret, fichier `.env`, audio ou base locale n’est suivi par Git.
