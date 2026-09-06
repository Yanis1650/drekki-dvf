# Vue 3 + Vite

This template should help get you started developing with Vue 3 in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about IDE Support for Vue in the [Vue Docs Scaling up Guide](https://vuejs.org/guide/scaling-up/tooling.html#ide-support).

## Vérifier la refonte

Depuis `frontend` : `npm ci`, `npm test`, `npm run check:charte`, `npm run build`.
L'audit des contrats et les décisions sont dans `../docs/FRONTEND_REDESIGN.md`.

Pour vérifier l'UI sans base DVF, lancer `node tests/fixtures/server.mjs` dans un
terminal, puis dans un autre terminal PowerShell :

```powershell
$env:VITE_API_BASE_URL='http://127.0.0.1:8010/api/v1'
npm run dev -- --host 127.0.0.1 --port 5174
```

Ce serveur contient uniquement des données fictives de test et n'est jamais
importé dans le bundle. Ne pas utiliser cette URL dans une configuration de
production. Fermer les deux processus après la vérification.
