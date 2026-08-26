import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'

// ApexCharts n'est PAS enregistre globalement : les deux composants qui
// l'utilisent (MarketTrendsChart, ParcelPriceChart) l'importent localement.
// L'enregistrer ici le forcait dans le chunk d'entree, soit ~200 Ko charges
// meme pour un visiteur qui n'ouvre jamais un graphique.
const app = createApp(App)
app.use(router)
app.mount('#app')
