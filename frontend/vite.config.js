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
        manualChunks: {
          maplibre: ['maplibre-gl'],
          charts: ['apexcharts', 'vue3-apexcharts'],
        },
      },
    },
  },
})
