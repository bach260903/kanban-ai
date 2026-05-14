import { DiffEditor } from '@monaco-editor/react'
import type { editor } from 'monaco-editor'
import { useCallback, useEffect, useRef } from 'react'

import styles from './diff-viewer.module.css'

export type DiffViewerProps = {
  /** Left/original pane — maps to API ``original_content`` (T065). */
  original: string
  /** Right/modified pane — maps to API ``modified_content``. */
  modified: string
  /** Monaco language id (default treats diff as plain text). */
  language?: string
  height?: number | string
  /** Optional label shown above the diff (e.g. primary file path). */
  title?: string
  /** Modified-side line click (US16 / T108): ``file`` from ``title`` or model URI, ``line`` from editor target. */
  onLineClick?: (file: string, line: number) => void
}

function fileNameFromModifiedModel(title: string | undefined, model: editor.ITextModel | null): string {
  const fromTitle = title?.trim()
  if (fromTitle) return fromTitle
  if (!model) return ''
  const { uri } = model
  const segments = uri.path.split('/').filter(Boolean)
  const tail = segments.length ? segments[segments.length - 1] : ''
  if (tail) return tail
  const p = uri.path.replace(/^\//, '')
  return p || ''
}

/**
 * Read-only Monaco diff for task review (US9 / T065).
 * Uses ``original`` / ``modified`` from ``GET .../tasks/{id}/diff`` — no client-side patch parsing.
 */
export function DiffViewer({
  original,
  modified,
  language = 'plaintext',
  height = '50vh',
  title,
  onLineClick,
}: DiffViewerProps) {
  const mouseDisposableRef = useRef<{ dispose: () => void } | null>(null)
  const onLineClickRef = useRef(onLineClick)
  const titleRef = useRef(title)

  onLineClickRef.current = onLineClick
  titleRef.current = title

  useEffect(() => {
    return () => {
      mouseDisposableRef.current?.dispose()
      mouseDisposableRef.current = null
    }
  }, [])

  const onDiffMount = useCallback((diffEditor: editor.IStandaloneDiffEditor) => {
    mouseDisposableRef.current?.dispose()
    mouseDisposableRef.current = null

    const modifiedEditor = diffEditor.getModifiedEditor()
    mouseDisposableRef.current = modifiedEditor.onMouseDown((e) => {
      if (!onLineClickRef.current) return
      if (e.event.browserEvent.button !== 0) return
      const pos = e.target.position
      if (!pos || pos.lineNumber < 1) return
      const model = modifiedEditor.getModel()
      const file = fileNameFromModifiedModel(titleRef.current, model) || '(modified)'
      onLineClickRef.current(file, pos.lineNumber)
    })
  }, [])

  return (
    <section className={styles.root} aria-label={title ?? 'Code diff'}>
      {title ? (
        <header className={styles.header}>
          <span>{title}</span>
          <span className={styles.badge} aria-hidden>
            Side by side
          </span>
        </header>
      ) : null}
      <div className={styles.editor}>
        <DiffEditor
          height={height}
          language={language}
          original={original}
          modified={modified}
          onMount={(editor) => {
            onDiffMount(editor)
          }}
          options={{
            readOnly: true,
            originalEditable: false,
            renderSideBySide: true,
            enableSplitViewResizing: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            automaticLayout: true,
            wordWrap: 'on',
            lineNumbers: 'on',
            renderOverviewRuler: true,
            ignoreTrimWhitespace: false,
          }}
        />
      </div>
    </section>
  )
}
