# Stratégie de tests automatisés

La qualité est contrôlée à chaque pull request et à chaque push vers `main` ou `develop`.

## Périmètre

- backend : tests Pytest, lint Ruff et couverture du code applicatif ;
- frontend : tests Vitest/Testing Library, couverture des modules testés et build Vite ;
- Teams : validation automatisée des contraintes essentielles du manifeste.

## Commandes reproductibles

```bash
cd server
pip install -r requirements-dev.txt
ruff check app tests
pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=75

cd ../web
npm install
npm test
npm run build

cd ..
node scripts/validate-teams-manifest.mjs
```

## Interprétation des résultats

Un workflow vert prouve que les contrôles automatisés configurés ont réussi sur le commit testé. Il ne prouve pas l'absence absolue d'anomalies. Les rapports de couverture rendent le périmètre auditable et les seuils empêchent une régression silencieuse.
