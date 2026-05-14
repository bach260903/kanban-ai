import { isAxiosError } from 'axios'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '../components/atoms/button'
import { Spinner } from '../components/atoms/spinner'
import { DocumentEditor } from '../components/molecules/document-editor'
import { getConstitution, updateConstitution } from '../services/project-api'

import pageShell from './page-shell.module.css'
import styles from './constitution-editor.module.css'

function errorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    return error.message
  }
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}

export default function ConstitutionEditor() {
  const { id } = useParams()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [content, setContent] = useState('')
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (!id) {
        setError('Project ID is missing from URL.')
        setLoading(false)
        return
      }
      try {
        setLoading(true)
        setError(null)
        const response = await getConstitution(id)
        if (!cancelled) {
          setContent(response.content)
          setLastSavedAt(response.updated_at)
        }
      } catch (err) {
        if (!cancelled) setError(errorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [id])

  async function onSave() {
    if (!id) return
    try {
      setSaving(true)
      setError(null)
      const response = await updateConstitution(id, content)
      setLastSavedAt(response.updated_at)
      setStatusMessage('Saved successfully.')
      setTimeout(() => setStatusMessage(null), 2500)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const savedText = useMemo(() => {
    if (!lastSavedAt) return 'Not saved yet'
    const parsed = new Date(lastSavedAt)
    return Number.isNaN(parsed.getTime()) ? lastSavedAt : `Last saved: ${parsed.toLocaleString()}`
  }, [lastSavedAt])

  return (
    <div className={pageShell.shell}>
      <h1 className={pageShell.title}>Constitution</h1>
      <p className={pageShell.lead}>Define project rules and standards for every agent run.</p>
      <nav className={pageShell.nav} aria-label="Constitution navigation">
        <Link to="/projects">All projects</Link>
        {id ? <Link to={`/projects/${id}`}>Workspace</Link> : null}
      </nav>

      {loading ? (
        <p className={styles.status}>
          <Spinner aria-label="Loading constitution" /> Loading constitution...
        </p>
      ) : (
        <>
          <DocumentEditor value={content} onChange={setContent} height="50vh" />
          <div className={styles.actions}>
            <Button variant="primary" onClick={onSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </Button>
            <span className={styles.status}>{savedText}</span>
          </div>
        </>
      )}

      {statusMessage ? <p className={`${styles.status} ${styles.success}`}>{statusMessage}</p> : null}
      {error ? <p className={`${styles.status} ${styles.error}`}>{error}</p> : null}
    </div>
  )
}
