import type { CodingBackend } from '../../types'

import styles from './badge.module.css'

type BackendBadgeProps = {
  backend: CodingBackend
  className?: string
}

const BACKEND_TONE: Record<CodingBackend, keyof typeof styles> = {
  groq: 'neutral',
  claude_code: 'warn',
  openai: 'success',
  gemini: 'info',
}

const BACKEND_LABEL: Record<CodingBackend, string> = {
  groq: 'Groq',
  claude_code: 'Claude Code',
  openai: 'OpenAI',
  gemini: 'Gemini',
}

export function BackendBadge({ backend, className }: BackendBadgeProps) {
  const tone = BACKEND_TONE[backend] ?? 'neutral'
  const label = BACKEND_LABEL[backend] ?? backend
  const merged = [styles.badge, styles[tone], className].filter(Boolean).join(' ')
  return <span className={merged}>{label}</span>
}
