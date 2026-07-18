export default defineNuxtConfig({
  devtools: { enabled: false },
  modules: ['@pinia/nuxt', '@element-plus/nuxt'],
  css: ['element-plus/dist/index.css'],
  vite: {
    server: {
      host: '0.0.0.0',
      hmr: {
        host: 'localhost',
        port: 3000,
      },
      watch: {
        usePolling: true,
        interval: 1000,
      },
      proxy: {
        '/api': {
          target: 'http://backend:8000',
          changeOrigin: true,
        }
      }
    }
  },
  app: {
    head: {
      title: 'ResAgent — 智能简历筛选',
      meta: [{ charset: 'utf-8' }, { name: 'viewport', content: 'width=device-width, initial-scale=1' }]
    }
  }
})
