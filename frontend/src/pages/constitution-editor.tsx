import { isAxiosError } from 'axios'
import { ChevronLeft, Loader2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '../components/atoms/button'
import { Spinner } from '../components/atoms/spinner'
import { DocumentEditor } from '../components/molecules/document-editor'
import { getConstitution, getProject, updateConstitution } from '../services/project-api'
import { useProjectStore } from '../store/project-store'
import { relativeTime } from '../utils/relative-time'

import pageShell from './page-shell.module.css'
import styles from './constitution-editor.module.css'

const CONSTITUTION_PLACEHOLDER = `# Project Constitution

## Coding Standards
- Use TypeScript strict mode
- Prefer functional components and hooks
- Run tests before every commit

## Agent Behavior
- Agents must read this constitution before each run
- Refuse changes that violate listed standards
- Surface deviations in the audit log

## Review Criteria
- All code changes require diff review
- Reviewer agent must approve before merge
- Reject PRs without tests for new behavior
`

function errorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    return error.message
  }
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}

type SaveState = 'idle' | 'dirty' | 'saving' | 'saved'

export default function ConstitutionEditor() {
  const { id } = useParams()
  const currentProject = useProjectStore((s) => s.currentProject)
  const setCurrentProject = useProjectStore((s) => s.setCurrentProject)
  const projectName = currentProject?.id === id ? currentProject?.name : null

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [content, setContent] = useState('')
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const initialContentRef = useRef<string>('')

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
        const [response, project] = await Promise.all([
          getConstitution(id),
          currentProject?.id === id
            ? Promise.resolve(currentProject)
            : getProject(id).catch(() => null),
        ])
        if (!cancelled) {
          setContent(response.content)
          initialContentRef.current = response.content
          setLastSavedAt(response.updated_at)
          setSaveState('idle')
          if (project && currentProject?.id !== id) setCurrentProject(project)
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
  }, [id, currentProject, setCurrentProject])

  useEffect(() => {
    if (loading) return
    if (content === initialContentRef.current) {
      setSaveState((prev) => (prev === 'saved' ? 'saved' : 'idle'))
    } else {
      setSaveState('dirty')
    }
  }, [content, loading])

  async function onSave() {
    if (!id) return
    try {
      setSaving(true)
      setSaveState('saving')
      setError(null)
      const response = await updateConstitution(id, content)
      setLastSavedAt(response.updated_at)
      initialContentRef.current = content
      setSaveState('saved')
      setStatusMessage('Saved successfully.')
      setTimeout(() => setStatusMessage(null), 2500)
    } catch (err) {
      setError(errorMessage(err))
      setSaveState('dirty')
    } finally {
      setSaving(false)
    }
  }

  const savedLabel = useMemo(() => {
    if (saveState === 'saving') return 'Saving…'
    if (saveState === 'dirty') return 'Unsaved changes'
    if (!lastSavedAt) return 'Not saved yet'
    return `Last saved ${relativeTime(lastSavedAt)}`
  }, [saveState, lastSavedAt])

  return (
    <div className={pageShell.shell}>
      <nav className={styles.breadcrumb} aria-label="Constitution navigation">
        <Link to="/projects" className={styles.breadcrumbBack}>
          <ChevronLeft size={16} aria-hidden="true" />
          All projects
        </Link>
        <span className={styles.breadcrumbSep} aria-hidden="true">
          /
        </span>
        {id ? (
          <Link to={`/projects/${id}`} className={styles.breadcrumbLink}>
            {projectName ?? 'Workspace'}
          </Link>
        ) : (
          <span className={styles.breadcrumbLink}>Workspace</span>
        )}
        <span className={styles.breadcrumbSep} aria-hidden="true">
          /
        </span>
        <span className={styles.breadcrumbCurrent} aria-current="page">
          Constitution
        </span>
      </nav>

      <h1 className={pageShell.title}>Constitution</h1>
      <p className={pageShell.lead}>Define project rules and standards for every agent run.</p>

      {loading ? (
        <p className={styles.status}>
          <Spinner aria-label="Loading constitution" /> Loading constitution...
        </p>
      ) : (
        <>
          <div className={styles.toolbar}>
            <div className={styles.saveIndicator} aria-live="polite">
              {saveState === 'saving' ? (
                <Loader2 className={styles.spin} size={14} aria-hidden="true" />
              ) : (
                <span
                  aria-hidden="true"
                  className={[
                    styles.dot,
                    saveState === 'dirty' ? styles.dotDirty : '',
                    saveState === 'saved' || saveState === 'idle' ? styles.dotSaved : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                />
              )}
              <span className={styles.status}>{savedLabel}</span>
            </div>
            <Button variant="primary" onClick={onSave} disabled={saving || saveState === 'idle' || saveState === 'saved'}>
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </div>
          <div className={styles.editorWrap}>
            <DocumentEditor
              value={content}
              onChange={setContent}
              height="55vh"
              ariaLabel="Constitution editor"
            />
            {!content.trim() ? (
              <pre className={styles.placeholder} aria-hidden="true">
                {CONSTITUTION_PLACEHOLDER}
              </pre>
            ) : null}
          </div>
        </>
      )}

      {statusMessage ? <p className={`${styles.status} ${styles.success}`}>{statusMessage}</p> : null}
      {error ? <p className={`${styles.status} ${styles.error}`}>{error}</p> : null}
    </div>
  )
}
