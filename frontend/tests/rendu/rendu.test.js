/**
 * Test de rendu : la carte et les graphiques s'affichent-ils vraiment ?
 *
 * Les 36 tests unitaires portent sur la logique de domaine. Ils ne montent ni
 * MapLibre ni ApexCharts, et ne font jamais naviguer le routeur. Un build vert
 * et une suite verte ne disent donc rien de ce que voit l'utilisateur.
 *
 * Ce trou a laisse passer une regression reelle : la montee de MapLibre en v6
 * compilait, passait les 36 tests et n'emettait aucune erreur de console — mais
 * la carte se chargeait vide, sans semis de mutations ni cercle de perimetre.
 * Seule une mesure des pixels reellement peints l'a vue.
 *
 * Le test monte donc la build de production contre le serveur de fixtures,
 * compte les pixels aux couleurs de la charte, et exerce la navigation par clic.
 *
 * Les seuils sont cales sur les fixtures, pas sur la production : douze
 * mutations fictives, aucun fond parcellaire. Ils verifient qu'il y a quelque
 * chose, pas combien.
 *
 * Voir docs/adr/0006-verifier-le-rendu-pas-seulement-le-build.md
 */
import assert from 'node:assert/strict';
import { after, before, describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { build, preview } from 'vite';
import { FIXTURE_PORT, createFixtureServer } from '../fixtures/server.mjs';

const PREVIEW_PORT = 4183;
const OUT_DIR = 'dist-rendu';
const ROOT = fileURLToPath(new URL('../..', import.meta.url));

// Marge appliquee au canvas avant mesure : le rail de droite porte lui aussi
// la rampe ocre et des liens bleus. Une zone figee en dur y debordait, et le
// test passait alors meme quand la carte etait vide — il ne mesurait plus la
// carte mais sa legende.
const MARGE = 8;

// Seuils de rendu, en pourcentage des pixels du canvas. Voir le commentaire de
// l'assertion qui les emploie pour les mesures dont ils sont issus.
const SEUIL_OCRE = 0.25;
const SEUIL_BLEU = 0.15;

let fixtures;
let previewServer;
let browser;
let page;

/**
 * Part des pixels de donnee et d'interface dans une zone.
 *
 * La mesure passe par une capture reinjectee dans un canvas 2D : le canvas de
 * MapLibre est un contexte WebGL sans `preserveDrawingBuffer`, dont
 * `getImageData` ne rend rien d'exploitable.
 */
async function mesurePixels() {
  const box = await page.locator('canvas.maplibregl-canvas').boundingBox();
  assert.ok(box, 'aucun canvas MapLibre a mesurer');
  const clip = {
    x: box.x + MARGE,
    y: box.y + MARGE,
    width: box.width - 2 * MARGE,
    height: box.height - 2 * MARGE,
  };
  const capture = await page.screenshot({ clip });
  return page.evaluate(async (dataUrl) => {
    const img = new Image();
    img.src = dataUrl;
    await img.decode();
    const canvas = document.createElement('canvas');
    canvas.width = img.width;
    canvas.height = img.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
    let ocre = 0;
    let bleu = 0;
    for (let i = 0; i < data.length; i += 4) {
      const [r, g, b] = [data[i], data[i + 1], data[i + 2]];
      // Le fond de carte est desature : tout pixel colore vient de la donnee
      // ou de l'interface.
      if (Math.max(r, g, b) - Math.min(r, g, b) < 18) continue;
      if (r > b + 25 && g > b + 10) ocre += 1;
      else if (b > r + 25) bleu += 1;
    }
    const total = data.length / 4;
    return { ocre: (100 * ocre) / total, bleu: (100 * bleu) / total };
  }, `data:image/png;base64,${capture.toString('base64')}`);
}

before(async () => {
  fixtures = createFixtureServer();
  await new Promise((resolve) => fixtures.listen(FIXTURE_PORT, '127.0.0.1', resolve));

  // L'URL de l'API est figee a la compilation : on la remplace ici plutot que
  // de dependre d'un fichier .env, qui ne serait pas le meme d'une machine a
  // l'autre.
  await build({
    root: ROOT,
    logLevel: 'warn',
    define: {
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(
        `http://127.0.0.1:${FIXTURE_PORT}/api/v1`,
      ),
    },
    build: { outDir: OUT_DIR, emptyOutDir: true },
  });

  previewServer = await preview({
    root: ROOT,
    logLevel: 'warn',
    build: { outDir: OUT_DIR },
    // Hote explicite : sans lui, Vite n'ecoute que sur ::1 et la connexion en
    // IPv4 est refusee — le comportement differe d'un runner a l'autre.
    preview: { host: '127.0.0.1', port: PREVIEW_PORT, strictPort: true },
  });

  browser = await chromium.launch({
    // Sans rendu logiciel, le canvas WebGL reste vide sur un runner sans GPU.
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'],
  });
  page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

  const erreurs = [];
  page.on('console', (m) => m.type() === 'error' && erreurs.push(m.text()));
  page.on('pageerror', (e) => erreurs.push(String(e)));
  page.erreurs = erreurs;

  await page.goto(`http://127.0.0.1:${PREVIEW_PORT}/`, { waitUntil: 'load' });
  // Le fond de carte charge des tuiles en continu : `networkidle` n'arrive
  // jamais. On laisse le style se poser, puis on mesure.
  await page.waitForSelector('canvas.maplibregl-canvas', { timeout: 30_000 });
  await page.waitForTimeout(6000);
});

after(async () => {
  await browser?.close();
  await previewServer?.close();
  await new Promise((resolve) => fixtures?.close(resolve));
});

describe('rendu de la carte', () => {
  it('monte un canvas MapLibre dimensionne', async () => {
    const box = await page.locator('canvas.maplibregl-canvas').boundingBox();
    assert.ok(box, 'aucun canvas MapLibre');
    assert.ok(box.width > 400 && box.height > 300, `canvas trop petit : ${box.width}x${box.height}`);
  });

  it('peint les mutations et le perimetre, pas seulement le fond', async () => {
    const { ocre, bleu } = await mesurePixels();
    // C'est precisement cette assertion que la montee MapLibre 6 faisait
    // tomber. Les seuils sont cales entre deux mesures reelles sur ces
    // fixtures : 0,455 % d'ocre et 0,333 % de bleu quand la carte rend, 0,060 %
    // et 0,072 % quand elle est vide. La marge est d'un facteur deux de chaque
    // cote — assez pour absorber l'antialiasing, pas assez pour laisser passer
    // une carte muette.
    assert.ok(ocre >= SEUIL_OCRE, `mutations non peintes : ${ocre.toFixed(3)} % d'ocre, seuil ${SEUIL_OCRE} %`);
    assert.ok(bleu >= SEUIL_BLEU, `perimetre non trace : ${bleu.toFixed(3)} % de bleu, seuil ${SEUIL_BLEU} %`);
  });

  it('affiche les indicateurs du perimetre', async () => {
    const pied = await page.getByLabel('Indicateurs du périmètre DVF').innerText();
    assert.match(pied, /mutations/);
    assert.match(pied, /Prix médian au m²/);
    assert.match(pied, /valeurs exclues/);
  });
});

describe('navigation et graphiques', () => {
  it('bascule sur Marché par un clic et trace les séries', async () => {
    await page.getByRole('link', { name: 'Marché', exact: true }).click();
    await page.waitForTimeout(4000);
    assert.match(page.url(), /\/marche$/, 'le routeur n’a pas change de route');

    const series = await page.locator('.apexcharts-series').count();
    assert.ok(series >= 2, `series non tracees (${series})`);

    // La charte exige que chaque point porte sa valeur ecrite : une courbe
    // qu'il faut survoler n'est lisible ni a l'impression, ni au clavier.
    const valeurs = await page.locator('.apexcharts-datalabels text').count();
    assert.ok(valeurs >= 4, `valeurs non ecrites sur les points (${valeurs})`);
  });

  it('revient à la carte sans perdre le rendu', async () => {
    await page.getByRole('link', { name: 'Dossiers', exact: true }).click();
    await page.waitForTimeout(1500);
    assert.match(page.url(), /\/dossiers$/);

    await page.getByRole('link', { name: 'Carte', exact: true }).click();
    await page.waitForSelector('canvas.maplibregl-canvas', { timeout: 30_000 });
    await page.waitForTimeout(6000);

    const { ocre } = await mesurePixels();
    assert.ok(ocre >= SEUIL_OCRE, `carte vide apres retour : ${ocre.toFixed(3)} % d'ocre`);
  });
});

describe('console', () => {
  it('ne laisse passer aucune erreur', () => {
    assert.deepEqual([...new Set(page.erreurs)], []);
  });
});
