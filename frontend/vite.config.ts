import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

const BACKEND_TARGET = process.env.VITE_BACKEND_TARGET ?? 'http://localhost:4010';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': {
        target: BACKEND_TARGET,
        changeOrigin: true,
      },
      '/ws': {
        target: BACKEND_TARGET.replace(/^http/, 'ws'),
        ws: true,
        changeOrigin: true,
      },
      '/rendered': {
        target: BACKEND_TARGET,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    target: 'es2022',
    chunkSizeWarningLimit: 1500,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // Vitest only handles unit tests under `src/`. Playwright owns `tests/`.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['tests/**', 'node_modules/**', 'dist/**', 'e2e/**'],
  },
});
