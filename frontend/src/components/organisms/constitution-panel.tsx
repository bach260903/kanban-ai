import { useEffect, useState } from 'react'

import { DocumentEditor } from '../molecules/document-editor'
import { getConstitution, updateConstitution } from '../../services/project-api'

import styles from './constitution-panel.module.css'

type ConstitutionPanelProps = {
  projectId: string
}

export function ConstitutionPanel({ projectId }: ConstitutionPanelProps) {
  const [content, setContent] = useState('')
  const [savedContent, setSavedContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await getConstitution(projectId)
        if (!cancelled) {
          setContent(res.content)
          setSavedContent(res.content)
          if (res.updated_at) {
            setLastSavedAt(new Date(res.updated_at).toLocaleString())
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load constitution.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [projectId])

  async function handleSave() {
    try {
      setSaving(true)
      setStatusMessage(null)
      setError(null)
      const res = await updateConstitution(projectId, content)
      setSavedContent(content)
      setStatusMessage('Saved')
      if (res.updated_at) {
        setLastSavedAt(new Date(res.updated_at).toLocaleString())
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save constitution.')
    } finally {
      setSaving(false)
    }
  }

  const isDirty = content !== savedContent

  if (loading) {
    return <p className={styles.loading}>Loading constitution…</p>
  }

  return (
    <div className={styles.panel}>
      <div className={styles.toolbar}>
        <span className={styles.title}>Constitution</span>
        <div className={styles.toolbarRight}>
          {isDirty ? <span className={styles.dirtyIndicator}>Unsaved changes</span> : null}
          {statusMessage && !isDirty ? (
            <span className={styles.status}>
              {statusMessage}
              {lastSavedAt ? ` · ${lastSavedAt}` : ''}
            </span>
          ) : null}
          <button
            type="button"
            className={styles.saveBtn}
            onClick={handleSave}
            disabled={saving || !isDirty}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
      {error ? <p className={styles.error}>{error}</p> : null}
      <div className={styles.editorWrap}>
        <DocumentEditor
          value={content}
          onChange={setContent}
          height="100%"
        />
      </div>
    </div>
  )
}
