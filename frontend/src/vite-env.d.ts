/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  /** Path (e.g. `/`) or absolute URL for 401 responses */
  readonly VITE_401_REDIRECT?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
