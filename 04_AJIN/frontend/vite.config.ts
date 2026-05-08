import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Plotly.js v3 번들 내부의 Node.js `global` 참조를 브라우저용 globalThis 로 치환.
  // 미적용 시 plotly__js.js 평가 단계에서 "ReferenceError: global is not defined" 발생.
  define: {
    global: 'globalThis',
  },
  // @rhwp/core (WASM): pre-bundle 제외 (런타임 import 시 동적 로드).
  optimizeDeps: {
    exclude: ['@rhwp/core'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@api': path.resolve(__dirname, './src/api'),
      '@components': path.resolve(__dirname, './src/components'),
      '@routes': path.resolve(__dirname, './src/routes'),
      '@store': path.resolve(__dirname, './src/store'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@types': path.resolve(__dirname, './src/types'),
      '@lib': path.resolve(__dirname, './src/lib'),
      '@i18n': path.resolve(__dirname, './src/i18n'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('@rhwp')) return 'rhwp-wasm';
            if (id.includes('react-plotly') || id.includes('plotly.js')) return 'plotly';
            if (id.includes('leaflet')) return 'leaflet';
            if (id.includes('i18next')) return 'i18n';
            if (
              id.includes('react-router') ||
              id.includes('/react/') ||
              id.includes('/react-dom/')
            ) {
              return 'react-vendor';
            }
          }
          return undefined;
        },
      },
    },
  },
});
