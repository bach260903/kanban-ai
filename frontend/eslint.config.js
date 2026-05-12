import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import { FlatCompat } from '@eslint/eslintrc'
import js from '@eslint/js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)

const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
})

const eslintrc = require('./.eslintrc.json')

export default [
  { ignores: ['dist', 'node_modules', 'coverage'] },
  ...compat.config(eslintrc),
]
