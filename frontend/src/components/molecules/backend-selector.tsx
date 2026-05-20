import { useEffect, useState } from 'react'

import { getAvailableBackends } from '../../services/project-api'
import type { CodingBackend } from '../../types'

type BackendOption = {
  value: CodingBackend
  label: string
}

const ALL_BACKENDS: BackendOption[] = [
  { value: 'groq', label: 'Groq (default)' },
  { value: 'claude_code', label: 'Claude Code' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'gemini', label: 'Gemini' },
]

type BackendSelectorProps = {
  value: CodingBackend
  onChange: (value: CodingBackend) => void
  disabled?: boolean
  id?: string
}

export function BackendSelector({ value, onChange, disabled, id }: BackendSelectorProps) {
  const [unavailable, setUnavailable] = useState<Set<string>>(new Set())

  useEffect(() => {
    getAvailableBackends()
      .then((data) => {
        const set = new Set(data.unavailable.map((u: { backend: string }) => u.backend))
        setUnavailable(set)
      })
      .catch(() => {})
  }, [])

  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value as CodingBackend)}
      disabled={disabled}
      aria-label="AI Coding Backend"
    >
      {ALL_BACKENDS.map((opt) => (
        <option
          key={opt.value}
          value={opt.value}
          disabled={unavailable.has(opt.value)}
          title={unavailable.has(opt.value) ? 'Not configured' : undefined}
        >
          {opt.label}{unavailable.has(opt.value) ? ' (not configured)' : ''}
        </option>
      ))}
    </select>
  )
}
