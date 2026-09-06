import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      'vue': 'vue/dist/vue.esm-bundler.js'
    }
  },
  build: {
    rollupOptions: {
      output: {
        // MapLibre et ApexCharts pesent chacun plusieurs centaines de Ko et
        // changent rarement : les isoler leur donne un cache navigateur propre,
        // que les deploiements applicatifs n'invalident pas.
        // La forme objet, acceptee jusqu'a Vite 7, est refusee par Vite 8 :
        // « manualChunks is not a function ». La forme fonction est comprise
        // par les deux, et exprime le meme decoupage par chemin de module.
        manualChunks(id) {
          if (id.includes('node_modules/maplibre-gl')) return 'maplibre';
          if (id.includes('node_modules/apexcharts')) return 'charts';
          if (id.includes('node_modules/vue3-apexcharts')) return 'charts';
        },
      },
    },
  },
})
