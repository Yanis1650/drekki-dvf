import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  {
    path: '/',
    name: 'map',
    component: () => import('./views/MapView.vue'),
  },
  {
    path: '/marche',
    name: 'market',
    component: () => import('./views/MarketView.vue'),
  },
  {
    path: '/rapports',
    name: 'reports',
    // placeholder — full view coming later
    component: () => import('./views/MarketView.vue'),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
