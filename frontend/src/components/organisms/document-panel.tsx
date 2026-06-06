import { isAxiosError } from 'axios'
import { CheckCircle2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Badge } from '../atoms/badge'
import { Button } from '../atoms/button'
import { Spinner } from '../atoms/spinner'
import { DocumentEditor } from '../molecules/document-editor'
import { useDocument } from '../../hooks/use-document'
import { showErrorToast, showSuccessToast } from '../../lib/toast'
import type { DocumentListItem } from '../../services/document-api'
import {
  approveDocument,
  generatePlan,
  generateSpec,
  getAgentRun,
  getDocuments,
  reviseDocument,
  updateDocument,
} from '../../services/document-api'
import type { DocumentType } from '../../types'
import { ConfirmDialog } from '../molecules/confirm-dialog'

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
  const [isEditing, setIsEditing] = useState(false)
  const [draftContent, setDraftContent] = useState('')
  const [saveConfirmOpen, setSaveConfirmOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  const refreshDocuments = useCallback(
    async (options?: { signal?: AbortSignal; forceRefresh?: boolean }) => {
      setListError(null)
      try {
        if (documentType === 'SPEC') {
          const rows = await getDocuments(projectId, 'SPEC', options)
          setDocRows(rows)
          setSpecRowsForPlan([])
        } else {
          const [planRows, specRows] = await Promise.all([
            getDocuments(projectId, 'PLAN', options),
            getDocuments(projectId, 'SPEC', options),
          ])
          setDocRows(planRows)
          setSpecRowsForPlan(specRows)
        }
      } catch (e) {
        if (options?.signal?.aborted) return
        if (e instanceof DOMException && e.name === 'AbortError') return
        if (isAxiosError(e) && (e.code === 'ERR_CANCELED' || e.name === 'CanceledError')) return
        setListError(errorMessage(e))
        setDocRows([])
        if (documentType === 'PLAN') {
          setSpecRowsForPlan([])
        }
      }
    },
    [projectId, documentType],
  )

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    ;(async () => {
      setListLoading(true)
      await refreshDocuments({
        signal: controller.signal,
        forceRefresh: refreshKey > 0,
      })
      if (!cancelled) setListLoading(false)
    })()
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [refreshDocuments, refreshKey])

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
    const id = window.setInterval(() => void poll(), 5000)
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
      await refreshDocuments({ forceRefresh: true })
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
      // Refresh so the pre-created document row is in docRows immediately
      await refreshDocuments({ forceRefresh: true })
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
      await refreshDocuments({ forceRefresh: true })
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

  function startEditing() {
    setDraftContent(document?.content ?? '')
    setIsEditing(true)
    setActionError(null)
  }

  function cancelEditing() {
    setIsEditing(false)
    setDraftContent('')
    setSaveConfirmOpen(false)
  }

  function requestSaveConfirm() {
    if (!draftContent.trim()) {
      setActionError(`${docLabel} content cannot be empty.`)
      return
    }
    setSaveConfirmOpen(true)
  }

  async function confirmSaveSpec() {
    if (!activeDocumentId) return
    setActionError(null)
    setStatusMessage(null)
    try {
      setSaving(true)
      const force = displayStatus === 'approved'
      await updateDocument(projectId, activeDocumentId, draftContent, { force })
      await refreshDocuments({ forceRefresh: true })
      await refetch()
      setIsEditing(false)
      setSaveConfirmOpen(false)
      setDraftContent('')
      showSuccessToast(
        force
          ? `${docLabel} saved. Status reset to draft — please re-approve.`
          : `${docLabel} saved.`,
      )
      if (force) {
        setStatusMessage(
          `${docLabel} reverted to draft. Re-approve when you are done editing.`,
        )
        setTimeout(() => setStatusMessage(null), 6000)
      }
    } catch (e) {
      showErrorToast(errorMessage(e))
      setActionError(errorMessage(e))
    } finally {
      setSaving(false)
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
      await refreshDocuments({ forceRefresh: true })
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
  const canEditSpec =
    documentType === 'SPEC' &&
    Boolean(activeDocumentId) &&
    !isGenerating &&
    !listLoading &&
    (displayStatus === 'draft' ||
      displayStatus === 'revision_requested' ||
      displayStatus === 'approved')

  const combinedError = listError ?? actionError ?? (error ? errorMessage(error) : null)

  const showHilActions =
    Boolean(activeDocumentId) &&
    (displayStatus === 'draft' || displayStatus === 'revision_requested') &&
    !isGenerating &&
    !isEditing

  const panelTitle = documentType === 'SPEC' ? 'SPEC.md' : 'PLAN.md'

  return (
    <section className={styles.root} aria-labelledby={headingId}>
      <div className={styles.toolbar}>
        <h3 id={headingId} className={styles.title}>
          <span className={styles.breadcrumb} aria-hidden>
            Documents&nbsp;/&nbsp;
          </span>
          {panelTitle}
        </h3>
        {displayStatus ? (
          <span className={styles.statusGroup}>
            {displayStatus === 'approved' ? (
              <CheckCircle2 className={styles.statusIcon} aria-hidden="true" size={16} />
            ) : null}
            <Badge kind="document" status={displayStatus} role="status" />
          </span>
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
            <DocumentEditor
              value={isEditing ? draftContent : editorValue}
              onChange={isEditing ? setDraftContent : () => {}}
              readOnly={!isEditing || isGenerating}
              height="min(55vh, 520px)"
              ariaLabel={`${panelTitle} editor`}
            />
          </div>
          {canEditSpec && !isEditing ? (
            <div className={styles.actions}>
              <Button type="button" variant="secondary" onClick={startEditing} disabled={isGenerating}>
                Edit {docLabel}
              </Button>
              <Button type="button" variant="secondary" onClick={() => void refetch()} disabled={isGenerating}>
                Refresh
              </Button>
              <Button type="button" variant="secondary" disabled aria-disabled="true" title="Coming soon">
                Version history
              </Button>
            </div>
          ) : null}
          {isEditing ? (
            <div className={styles.actionBar} role="region" aria-label={`Edit ${docLabel}`}>
              <span className={styles.actionBarLabel}>Manual edit</span>
              <div className={styles.actionBarRow}>
                <Button type="button" onClick={requestSaveConfirm} disabled={saving || !draftContent.trim()}>
                  Save changes
                </Button>
                <Button type="button" variant="secondary" onClick={cancelEditing} disabled={saving}>
                  Cancel
                </Button>
              </div>
              {displayStatus === 'approved' ? (
                <p className={styles.muted}>
                  {docLabel} is approved. Saving will revert it to draft and require re-approval before
                  generating a new PLAN.
                </p>
              ) : null}
            </div>
          ) : null}
          <ConfirmDialog
            open={saveConfirmOpen}
            title={`Confirm save ${docLabel}`}
            message={
              displayStatus === 'approved'
                ? `${docLabel} is currently approved. Saving will revert it to draft and require re-approval. Continue?`
                : `Are you sure you want to save changes to ${docLabel}?`
            }
            confirmLabel="Save"
            confirmVariant="primary"
            busy={saving}
            onConfirm={() => void confirmSaveSpec()}
            onCancel={() => setSaveConfirmOpen(false)}
          />
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
        </>
      ) : null}
    </section>
  )
}
