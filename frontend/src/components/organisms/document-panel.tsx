import { isAxiosError } from 'axios'
import { useCallback, useEffect, useState } from 'react'

import { Button } from '../atoms/button'
import { Spinner } from '../atoms/spinner'
import { DocumentEditor } from '../molecules/document-editor'
import { useDocument } from '../../hooks/use-document'
import type { DocumentListItem } from '../../services/document-api'
import { approveDocument, generateSpec, getDocuments, reviseDocument } from '../../services/document-api'
import type { DocumentStatus } from '../../types'

import styles from './document-panel.module.css'

export type DocumentPanelProps = {
  projectId: string
}

function errorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    return err.message
  }
  if (err instanceof Error) return err.message
  return 'Something went wrong.'
}

function statusBadgeClass(status: DocumentStatus): string {
  if (status === 'approved') return `${styles.badge} ${styles.badgeApproved}`
  if (status === 'revision_requested') return `${styles.badge} ${styles.badgeRevision}`
  return styles.badge
}

export function DocumentPanel({ projectId }: DocumentPanelProps) {
  const [specRows, setSpecRows] = useState<DocumentListItem[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [intent, setIntent] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [pendingRunId, setPendingRunId] = useState<string | null>(null)
  const [revisionFeedback, setRevisionFeedback] = useState('')
  const [hilBusy, setHilBusy] = useState(false)

  const refreshSpecs = useCallback(async () => {
    setListError(null)
    try {
      const rows = await getDocuments(projectId, 'SPEC')
      setSpecRows(rows)
    } catch (e) {
      setListError(errorMessage(e))
      setSpecRows([])
    }
  }, [projectId])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setListLoading(true)
      await refreshSpecs()
      if (!cancelled) setListLoading(false)
    })()
    return () => {
      cancelled = true
    }
  }, [refreshSpecs])

  const latestSpec = specRows?.[0]
  const specDocumentId = latestSpec?.id

  const { document, agentRun, isGenerating, isLoading, error, refetch } = useDocument(projectId, specDocumentId, {
    agentRunId: pendingRunId,
  })

  useEffect(() => {
    if (agentRun && agentRun.status !== 'running') {
      setPendingRunId(null)
    }
  }, [agentRun])

  const displayStatus = document?.status ?? latestSpec?.status
  const showGenerate = !listLoading && specRows.length === 0
  const showHilActions =
    Boolean(specDocumentId) &&
    (displayStatus === 'draft' || displayStatus === 'revision_requested') &&
    !isGenerating

  async function onGenerateSpec() {
    setActionError(null)
    setStatusMessage(null)
    const trimmed = intent.trim()
    if (trimmed.length < 10) {
      setActionError('Intent must be at least 10 characters.')
      return
    }
    try {
      setSubmitting(true)
      const res = await generateSpec(projectId, { intent: trimmed })
      await refreshSpecs()
      setPendingRunId(res.agent_run_id)
      setIntent('')
      setStatusMessage('SPEC generation started. This may take up to a minute.')
      setTimeout(() => setStatusMessage(null), 4000)
    } catch (e) {
      setActionError(errorMessage(e))
    } finally {
      setSubmitting(false)
    }
  }

  async function onApproveSpec() {
    if (!specDocumentId) return
    setActionError(null)
    setStatusMessage(null)
    try {
      setHilBusy(true)
      await approveDocument(projectId, specDocumentId)
      await refreshSpecs()
      await refetch()
      setStatusMessage('SPEC approved.')
      setTimeout(() => setStatusMessage(null), 4000)
    } catch (e) {
      setActionError(errorMessage(e))
    } finally {
      setHilBusy(false)
    }
  }

  async function onRequestRevision() {
    if (!specDocumentId) return
    setActionError(null)
    setStatusMessage(null)
    const fb = revisionFeedback.trim()
    if (!fb) {
      setActionError('Enter revision feedback before submitting.')
      return
    }
    try {
      setHilBusy(true)
      const res = await reviseDocument(projectId, specDocumentId, fb)
      await refreshSpecs()
      setPendingRunId(res.agent_run_id)
      setRevisionFeedback('')
      await refetch()
      setStatusMessage('Revision requested. Regenerating SPEC…')
      setTimeout(() => setStatusMessage(null), 5000)
    } catch (e) {
      setActionError(errorMessage(e))
    } finally {
      setHilBusy(false)
    }
  }

  const editorValue = document?.content ?? ''
  const noopChange = useCallback(() => {}, [])

  const combinedError = listError ?? actionError ?? (error ? errorMessage(error) : null)

  return (
    <section className={styles.root} aria-labelledby="document-panel-heading">
      <div className={styles.toolbar}>
        <h2 id="document-panel-heading" className={styles.title}>
          SPEC.md
        </h2>
        {displayStatus ? (
          <span className={statusBadgeClass(displayStatus)} role="status">
            {displayStatus.replaceAll('_', ' ')}
          </span>
        ) : null}
      </div>

      {listLoading ? (
        <p className={styles.spinnerRow}>
          <Spinner aria-label="Loading documents" />
          Loading documents…
        </p>
      ) : null}

      {combinedError ? <p className={styles.error}>{combinedError}</p> : null}
      {statusMessage ? <p className={styles.success}>{statusMessage}</p> : null}

      {showGenerate ? (
        <div className={styles.empty}>
          <label className={styles.intentLabel} htmlFor="spec-intent">
            Intent
          </label>
          <textarea
            id="spec-intent"
            className={styles.intent}
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            placeholder="Describe what you want in the SPEC (min. 10 characters)…"
            minLength={10}
            maxLength={5000}
            disabled={submitting || isGenerating}
          />
          <div className={styles.actions}>
            <Button
              type="button"
              onClick={() => void onGenerateSpec()}
              disabled={submitting || isGenerating || intent.trim().length < 10}
            >
              Generate SPEC
            </Button>
            {submitting || isGenerating ? <Spinner aria-label="Starting generation" /> : null}
          </div>
          <p className={styles.muted}>No SPEC document yet for this project.</p>
        </div>
      ) : null}

      {!listLoading && specDocumentId ? (
        <>
          {isLoading && !document && !isGenerating ? (
            <p className={styles.spinnerRow}>
              <Spinner aria-label="Loading SPEC" />
              Loading SPEC…
            </p>
          ) : null}
          <div className={styles.editorWrap}>
            {isGenerating ? (
              <div className={styles.overlay}>
                <Spinner aria-label="Generating" />
                Generating…
              </div>
            ) : null}
            <DocumentEditor value={editorValue} onChange={noopChange} readOnly height="min(55vh, 520px)" />
          </div>
          {showHilActions ? (
            <div className={styles.actionBar} role="region" aria-label="Document review actions">
              <span className={styles.actionBarLabel}>Product owner review</span>
              <div className={styles.actionBarRow}>
                <Button type="button" onClick={() => void onApproveSpec()} disabled={hilBusy || isLoading}>
                  Approve
                </Button>
                {hilBusy ? <Spinner aria-label="Saving review" /> : null}
              </div>
              <label className={styles.intentLabel} htmlFor="spec-revision-feedback">
                Request revision
              </label>
              <textarea
                id="spec-revision-feedback"
                className={styles.revisionField}
                value={revisionFeedback}
                onChange={(e) => setRevisionFeedback(e.target.value)}
                placeholder="Describe what should change in the SPEC…"
                disabled={hilBusy}
                minLength={1}
              />
              <div className={styles.actions}>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void onRequestRevision()}
                  disabled={hilBusy || revisionFeedback.trim().length === 0}
                >
                  Submit revision
                </Button>
              </div>
            </div>
          ) : null}
          <div className={styles.actions}>
            <Button type="button" variant="secondary" onClick={() => void refetch()} disabled={isGenerating}>
              Refresh
            </Button>
          </div>
        </>
      ) : null}
    </section>
  )
}
