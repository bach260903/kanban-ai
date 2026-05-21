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
  test: {
    globals: true,
    environment: 'jsdom',
  },
})
