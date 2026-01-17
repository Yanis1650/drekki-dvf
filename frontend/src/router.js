import { createRouter, createWebHistory } from 'vue-router';

// Single route that captures all query params for deep linking
const routes = [
    {
        path: '/',
        name: 'home',
        // App.vue is the main component, no separate view needed
        component: () => import('./App.vue')
    }
];

const router = createRouter({
    history: createWebHistory(),
    routes
});

export default router;
