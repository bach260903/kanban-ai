import { DiffEditor } from '@monaco-editor/react'

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
}: DiffViewerProps) {
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
