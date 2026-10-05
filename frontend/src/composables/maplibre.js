/**
 * Point d'entrée unique de MapLibre dans l'application.
 *
 * MapLibre 6 découpe ses sources, GeoJSON compris, dans un worker qu'il charge
 * par URL. Derrière un bundler, il ne sait pas où ce fichier a été rangé : il
 * faut le lui dire par `setWorkerUrl`, avant de créer la moindre carte.
 *
 * Sans cet appel, la build de production demande
 * `/assets/maplibre-gl-worker.mjs`, que Vite n'émet pas. nginx répond alors
 * par index.html (repli SPA), le worker ne démarre jamais, et la carte
 * n'affiche que le fond IGN : ni mutations, ni périmètre, et aucune erreur
 * dans la console de la page. Seul le test de rendu le voit.
 *
 * `?worker&url` et non `?url` : le worker importe son voisin
 * `maplibre-gl-shared.mjs`, que `?url` n'émettrait pas.
 *
 * Référence : guide de migration MapLibre v5 → v6, « setWorkerUrl() is
 * bundler-only ».
 */
import { Map, NavigationControl, setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

setWorkerUrl(workerUrl);

export { Map as MaplibreMap, NavigationControl };
