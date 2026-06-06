/// <reference types="vitest/config" />
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const frontendRoot = path.dirname(fileURLToPath(import.meta.url))
// monaco-editor is hoisted to kanban-ai/node_modules (parent of frontend/)
const repoRoot = path.resolve(frontendRoot, '..')

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      allow: [frontendRoot, repoRoot],
    },
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws': { target: 'http://127.0.0.1:8000', ws: true, changeOrigin: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Monaco editor in its own chunk — loaded only when diff viewer opens
          if (id.includes('monaco-editor') || id.includes('@monaco-editor')) {
            return 'monaco'
          }
          // React core in a stable vendor chunk
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) {
            return 'react-vendor'
          }
          // Router + state in a shared chunk
          if (id.includes('react-router') || id.includes('zustand')) {
            return 'app-vendor'
          }
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
  },
})
