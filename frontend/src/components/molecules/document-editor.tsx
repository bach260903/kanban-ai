import Editor, { type OnMount } from '@monaco-editor/react'
import { useRef } from 'react'

type DocumentEditorProps = {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
  height?: number | string
  /**
   * Accessible label propagated to Monaco's hidden textarea. Required to
   * silence the Chrome a11y "form field should have an id or name" warning
   * and to give screen readers a meaningful label.
   */
  ariaLabel?: string
}

function slugify(label: string): string {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
}

export function DocumentEditor({
  value,
  onChange,
  readOnly = false,
  height = '60vh',
  ariaLabel = 'Markdown editor',
}: DocumentEditorProps) {
  const idRef = useRef<string>(`monaco-${slugify(ariaLabel)}-${Math.random().toString(36).slice(2, 8)}`)

  const handleMount: OnMount = (editor) => {
    // Monaco's internal textarea (for IME / keyboard input) has no id or
    // name by default which triggers a Chrome a11y warning. Patch all
    // textareas inside this editor's DOM so the input has both.
    const dom = editor.getDomNode()
    const textareas = dom?.querySelectorAll('textarea') ?? []
    textareas.forEach((textarea, idx) => {
      const id = `${idRef.current}-${idx}`
      textarea.setAttribute('id', id)
      textarea.setAttribute('name', id)
      if (!textarea.getAttribute('aria-label')) {
        textarea.setAttribute('aria-label', ariaLabel)
      }
    })
  }

  return (
    <Editor
      height={height}
      defaultLanguage="markdown"
      value={value}
      onChange={(next) => onChange(next ?? '')}
      onMount={handleMount}
      options={{
        readOnly,
        minimap: { enabled: false },
        wordWrap: 'on',
        lineNumbers: 'on',
        scrollBeyondLastLine: false,
        automaticLayout: true,
        ariaLabel,
      }}
    />
  )
}
