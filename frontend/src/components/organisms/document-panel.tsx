import { isAxiosError } from 'axios'
import { useCallback, useEffect, useState } from 'react'

import { Badge } from '../atoms/badge'
import { Button } from '../atoms/button'
import { Spinner } from '../atoms/spinner'
import { DocumentEditor } from '../molecules/document-editor'
import { useDocument } from '../../hooks/use-document'
import type { DocumentListItem } from '../../services/document-api'
import {
  approveDocument,
  generatePlan,
  generateSpec,
  getAgentRun,
  getDocuments,
  reviseDocument,
} from '../../services/document-api'
import type { DocumentStatus, DocumentType } from '../../types'

import styles from './document-panel.module.css'

export type DocumentPanelProps = {
  projectId: string
  documentType: DocumentType
  /** When SPEC approve auto-starts PLAN, parent passes the architect run id to the PLAN panel. */
  linkedAgentRunId?: string | null
  /** Bump to force document list refresh (e.g. after SPEC approve). */
  refreshKey?: number
  /** Called when SPEC approval starts PLAN generation in the background. */
  onPlanAutoStart?: (agentRunId: string) => void
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

export function DocumentPanel({
  projectId,
  documentType,
  linkedAgentRunId = null,
  refreshKey = 0,
  onPlanAutoStart,
}: DocumentPanelProps) {
  const [docRows, setDocRows] = useState<DocumentListItem[]>([])
  const [specRowsForPlan, setSpecRowsForPlan] = useState<DocumentListItem[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [intent, setIntent] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [pendingRunId, setPendingRunId] = useState<string | null>(null)
  const [revisionFeedback, setRevisionFeedback] = useState('')
  const [hilBusy, setHilBusy] = useState(false)

  const refreshDocuments = useCallback(async () => {
    setListError(null)
    try {
      if (documentType === 'SPEC') {
        const rows = await getDocuments(projectId, 'SPEC')
        setDocRows(rows)
        setSpecRowsForPlan([])
      } else {
        const [planRows, specRows] = await Promise.all([
          getDocuments(projectId, 'PLAN'),
          getDocuments(projectId, 'SPEC'),
        ])
        setDocRows(planRows)
        setSpecRowsForPlan(specRows)
      }
    } catch (e) {
      setListError(errorMessage(e))
      setDocRows([])
      if (documentType === 'PLAN') {
        setSpecRowsForPlan([])
      }
    }
  }, [projectId, documentType])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setListLoading(true)
      await refreshDocuments()
      if (!cancelled) setListLoading(false)
    })()
    return () => {
      cancelled = true
    }
  }, [refreshDocuments, refreshKey])

  useEffect(() => {
    if (refreshKey > 0) {
      void refreshDocuments()
    }
  }, [refreshKey, refreshDocuments])

  const latestSpecForGate = specRowsForPlan[0]
  const specApproved = latestSpecForGate?.status === 'approved'
  const activeDocumentId = docRows[0]?.id

  const trackedRunId = pendingRunId ?? (documentType === 'PLAN' ? linkedAgentRunId : null)

  const { document, agentRun, isGenerating, isLoading, error, refetch } = useDocument(
    projectId,
    activeDocumentId,
    { agentRunId: trackedRunId },
  )

  /** Poll linked PLAN run when PLAN row does not exist yet (auto-start after SPEC approve). */
  useEffect(() => {
    if (documentType !== 'PLAN' || !linkedAgentRunId || activeDocumentId) return undefined
    let cancelled = false
    const poll = async () => {
      try {
        const run = await getAgentRun(linkedAgentRunId)
        if (cancelled) return
        if (run.status !== 'running') {
          await refreshDocuments()
        }
      } catch {
        /* ignore */
      }
    }
    void poll()
    const id = window.setInterval(() => void poll(), 3000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [documentType, linkedAgentRunId, activeDocumentId, refreshDocuments])

  useEffect(() => {
    if (agentRun && agentRun.status !== 'running') {
      setPendingRunId(null)
    }
  }, [agentRun])

  const agentFailed =
    agentRun != null && (agentRun.status === 'failure' || agentRun.status === 'timeout')
  const agentFailureDetail = (() => {
    if (!agentFailed || agentRun?.result == null || typeof agentRun.result !== 'object') {
      return null
    }
    const r = agentRun.result as Record<string, unknown>
    const msg = r.error ?? r.message ?? r.detail
    return typeof msg === 'string' && msg.trim() !== '' ? msg.trim() : null
  })()

  const displayStatus = document?.status ?? docRows[0]?.status
  const showGenerateSpec = documentType === 'SPEC' && !listLoading && docRows.length === 0
  const planAutoStarting =
    documentType === 'PLAN' && specApproved && Boolean(linkedAgentRunId) && isGenerating
  const showGeneratePlan =
    documentType === 'PLAN' &&
    !listLoading &&
    docRows.length === 0 &&
    specApproved &&
    !planAutoStarting
  const showPlanBlocked =
    documentType === 'PLAN' && !listLoading && docRows.length === 0 && !specApproved

  const docLabel = documentType === 'SPEC' ? 'SPEC' : 'PLAN'
  const headingId =
    documentType === 'SPEC' ? 'document-panel-spec-heading' : 'document-panel-plan-heading'
  const revisionFieldId = `${documentType.toLowerCase()}-revision-feedback`

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
      await refreshDocuments()
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

  async function onGeneratePlan() {
    setActionError(null)
    setStatusMessage(null)
    try {
      setSubmitting(true)
      const res = await generatePlan(projectId)
      await refreshDocuments()
      setPendingRunId(res.agent_run_id)
      setStatusMessage('PLAN generation started. This may take up to a minute.')
      setTimeout(() => setStatusMessage(null), 5000)
    } catch (e) {
      setActionError(errorMessage(e))
    } finally {
      setSubmitting(false)
    }
  }

  async function onApprove() {
    if (!activeDocumentId) return
    setActionError(null)
    setStatusMessage(null)
    try {
      setHilBusy(true)
      const res = await approveDocument(projectId, activeDocumentId)
      await refreshDocuments()
      await refetch()
      if (documentType === 'SPEC' && res.plan_generation_started && res.plan_agent_run_id) {
        onPlanAutoStart?.(res.plan_agent_run_id)
        setStatusMessage(
          'SPEC approved. PLAN is being generated automatically for your review (see PLAN panel).',
        )
      } else {
        setStatusMessage(documentType === 'SPEC' ? 'SPEC approved.' : 'PLAN approved.')
      }
      setTimeout(() => setStatusMessage(null), 6000)
    } catch (e) {
      setActionError(errorMessage(e))
    } finally {
      setHilBusy(false)
    }
  }

  async function onRequestRevision() {
    if (!activeDocumentId) return
    setActionError(null)
    setStatusMessage(null)
    const fb = revisionFeedback.trim()
    if (!fb) {
      setActionError('Enter revision feedback before submitting.')
      return
    }
    try {
      setHilBusy(true)
      const res = await reviseDocument(projectId, activeDocumentId, fb)
      await refreshDocuments()
      setPendingRunId(res.agent_run_id)
      setRevisionFeedback('')
      await refetch()
      setStatusMessage(
        documentType === 'SPEC'
          ? 'Revision requested. Regenerating SPEC…'
          : 'Revision requested. Regenerating PLAN…',
      )
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

  const showHilActions =
    Boolean(activeDocumentId) &&
    (displayStatus === 'draft' || displayStatus === 'revision_requested') &&
    !isGenerating

  const panelTitle = documentType === 'SPEC' ? 'SPEC.md' : 'PLAN.md'

  return (
    <section className={styles.root} aria-labelledby={headingId}>
      <div className={styles.toolbar}>
        <h2 id={headingId} className={styles.title}>
          {panelTitle}
        </h2>
        {displayStatus ? (
          <Badge kind="document" status={displayStatus} role="status" />
        ) : null}
      </div>

      {listLoading ? (
        <p className={styles.spinnerRow}>
          <Spinner aria-label={`Loading ${docLabel} documents`} />
          Loading documents…
        </p>
      ) : null}

      {combinedError ? <p className={styles.error}>{combinedError}</p> : null}
      {agentFailed ? (
        <p className={styles.error} role="alert">
          {docLabel} generation failed
          {agentFailureDetail ? `: ${agentFailureDetail}` : ''}. Check backend logs and{' '}
          <code>GROQ_API_KEY</code> / <code>GROQ_MODEL</code> in <code>.env</code>.
        </p>
      ) : null}
      {statusMessage ? <p className={styles.success}>{statusMessage}</p> : null}

      {showGenerateSpec ? (
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

      {showGeneratePlan ? (
        <div className={styles.empty}>
          <div className={styles.actions}>
            <Button type="button" onClick={() => void onGeneratePlan()} disabled={submitting || isGenerating}>
              Generate PLAN
            </Button>
            {submitting || isGenerating ? <Spinner aria-label="Starting PLAN generation" /> : null}
          </div>
          <p className={styles.muted}>
            SPEC is approved. Use Generate PLAN only if automatic generation did not start.
          </p>
        </div>
      ) : null}

      {planAutoStarting ? (
        <div className={styles.empty}>
          <p className={styles.spinnerRow}>
            <Spinner aria-label="Generating PLAN after SPEC approval" />
            Generating PLAN from approved SPEC…
          </p>
          <p className={styles.muted}>Review the draft here when generation finishes, then Approve PLAN.</p>
        </div>
      ) : null}

      {showPlanBlocked ? (
        <div className={styles.empty}>
          <p className={styles.muted}>
            {specRowsForPlan.length === 0
              ? 'Create a SPEC and approve it before generating a PLAN.'
              : 'Approve the SPEC to enable Generate PLAN.'}
          </p>
        </div>
      ) : null}

      {!listLoading && activeDocumentId ? (
        <>
          {isLoading && !document && !isGenerating ? (
            <p className={styles.spinnerRow}>
              <Spinner aria-label={`Loading ${docLabel}`} />
              Loading {docLabel}…
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
            <div className={styles.actionBar} role="region" aria-label={`${docLabel} review actions`}>
              <span className={styles.actionBarLabel}>Product owner review</span>
              <div className={styles.actionBarRow}>
                <Button type="button" onClick={() => void onApprove()} disabled={hilBusy || isLoading}>
                  Approve
                </Button>
                {hilBusy ? <Spinner aria-label="Saving review" /> : null}
              </div>
              <label className={styles.intentLabel} htmlFor={revisionFieldId}>
                Request revision
              </label>
              <textarea
                id={revisionFieldId}
                className={styles.revisionField}
                value={revisionFeedback}
                onChange={(e) => setRevisionFeedback(e.target.value)}
                placeholder={`Describe what should change in the ${docLabel}…`}
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
