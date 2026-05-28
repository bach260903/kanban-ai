import { isAxiosError } from 'axios'
import type { editor } from 'monaco-editor'
import { Code2, Eye } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { Button } from '../atoms/button'
import { Spinner } from '../atoms/spinner'
import { DiffViewer } from '../molecules/diff-viewer'
import { InlineCommentOverlay } from '../molecules/inline-comment-overlay'
import { SaveAsTemplateModal } from '../molecules/save-as-template-modal'
import { AiReviewPanel } from './ai-review-panel'
import { useAuth } from '../../contexts/auth-context'
import { getMembers } from '../../services/member-api'
import {
  approveTask,
  getDiff,
  getTaskComments,
  getTasks,
  groupedResponseToTaskColumns,
  moveTask,
  rejectTask,
} from '../../services/task-api'
import type { TaskDiffResponse } from '../../services/task-api'
import type { UseInlineCommentsReturn } from '../../hooks/use-inline-comments'
import { useReviewReport } from '../../services/review-api'
import { handleReviewStreamEvent } from '../../services/ws-handler'
import { useThoughtStream } from '../../hooks/use-thought-stream'
import { useTaskStore } from '../../store/task-store'

import styles from './review-panel.module.css'

function diffErrorMessage(err: unknown): string {
  if (isAxiosError(err) && err.response?.status === 404) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    return 'No diff available yet.'
  }
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    return err.message
  }
  if (err instanceof Error) return err.message
  return 'Unable to load diff.'
}

export type ReviewPanelProps = {
  projectId: string
  taskId: string
  inlineComments: UseInlineCommentsReturn
  onClose: () => void
}

/**
 * Code review HIL for a selected task in ``review`` (US9 / T066): diff + approve / reject.
 * Opened on demand when PO clicks a task in the Review column — not auto-shown.
 */
export function ReviewPanel({ projectId, taskId, inlineComments, onClose }: ReviewPanelProps) {
  const columns = useTaskStore((s) => s.columns)
  const setColumns = useTaskStore((s) => s.setColumns)

  const reviewTask = useMemo(
    () => columns.review.find((t) => t.id === taskId) ?? null,
    [columns.review, taskId],
  )

  const [diff, setDiff] = useState<TaskDiffResponse | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)
  const [diffError, setDiffError] = useState<string | null>(null)
  const [actionBusy, setActionBusy] = useState(false)
  const [rejectFeedback, setRejectFeedback] = useState('')
  const [modifiedEditor, setModifiedEditor] = useState<editor.IStandaloneCodeEditor | null>(null)
  const [highlightedLine, setHighlightedLine] = useState<{ file: string; line: number | null } | null>(null)
  const [saveTemplateOpen, setSaveTemplateOpen] = useState(false)
  const [canSaveTemplate, setCanSaveTemplate] = useState(false)

  const reviewState = useReviewReport(reviewTask?.id ?? null)
  const { user } = useAuth()
  const { events: streamEvents } = useThoughtStream(reviewTask?.id ?? null)

  useEffect(() => {
    if (!user) {
      setCanSaveTemplate(false)
      return
    }
    let cancelled = false
    void getMembers(projectId)
      .then((rows) => {
        if (cancelled) return
        const role = rows.find((m) => m.user_id === user.id)?.role
        setCanSaveTemplate(role === 'owner' || role === 'leader')
      })
      .catch(() => {
        if (!cancelled) setCanSaveTemplate(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectId, user])

  // Forward REVIEW_* WS events to the review state for optimistic updates
  useEffect(() => {
    if (streamEvents.length === 0) return
    const last = streamEvents[streamEvents.length - 1]
    if (last) handleReviewStreamEvent(last, reviewState.applyStreamEvent)
  }, [streamEvents, reviewState.applyStreamEvent])
  const {
    comments: inlineCommentRows,
    replaceFromApi,
    getCommentPayload,
  } = inlineComments
  const [activeCommentLine, setActiveCommentLine] = useState<number | null>(null)
  const [reviewTab, setReviewTab] = useState<'diff' | 'ai'>('diff')

  const refreshBoard = useCallback(async () => {
    const data = await getTasks(projectId)
    setColumns(groupedResponseToTaskColumns(data))
  }, [projectId, setColumns])

  const refreshInlineComments = useCallback(async () => {
    const tid = reviewTask?.id
    if (!tid) return
    try {
      const rows = await getTaskComments(tid)
      replaceFromApi(rows)
    } catch {
      replaceFromApi([])
    }
  }, [reviewTask?.id, replaceFromApi])

  useEffect(() => {
    if (!reviewTask) {
      setDiff(null)
      setDiffError(null)
      setDiffLoading(false)
      return
    }
    let cancelled = false
    setDiffLoading(true)
    setDiffError(null)
    setDiff(null)
    void (async () => {
      try {
        const d = await getDiff(projectId, reviewTask.id)
        if (!cancelled) setDiff(d)
      } catch (err) {
        if (!cancelled) setDiffError(diffErrorMessage(err))
      } finally {
        if (!cancelled) setDiffLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [projectId, reviewTask])

  useEffect(() => {
    if (!reviewTask || !diff) {
      replaceFromApi([])
      return
    }
    void refreshInlineComments()
  }, [reviewTask?.id, diff?.id, refreshInlineComments, replaceFromApi])

  useEffect(() => {
    setActiveCommentLine(null)
    setHighlightedLine(null)
  }, [diff?.id])

  useEffect(() => {
    if (!diff) {
      setModifiedEditor(null)
      setActiveCommentLine(null)
    }
  }, [diff])

  const onApprove = useCallback(async () => {
    if (!reviewTask) return
    setActionBusy(true)
    setDiffError(null)
    try {
      await approveTask(projectId, reviewTask.id)
      setRejectFeedback('')
      await refreshBoard()
      onClose()
    } catch (err) {
      setDiffError(diffErrorMessage(err))
    } finally {
      setActionBusy(false)
    }
  }, [projectId, reviewTask, refreshBoard, onClose])

  const onPermanentReject = useCallback(async () => {
    if (!reviewTask) return
    if (!window.confirm(`Permanently discard "${reviewTask.title}"? The task will move to the Rejected column and no agent retry will be triggered.`)) return
    setActionBusy(true)
    setDiffError(null)
    try {
      await moveTask(projectId, reviewTask.id, 'rejected')
      await refreshBoard()
      onClose()
    } catch (err) {
      setDiffError(diffErrorMessage(err))
    } finally {
      setActionBusy(false)
    }
  }, [projectId, reviewTask, refreshBoard, onClose])

  const onReject = useCallback(async () => {
    if (!reviewTask) return
    const fb = rejectFeedback.trim()
    if (!fb) return
    setActionBusy(true)
    setDiffError(null)
    try {
      await rejectTask(projectId, reviewTask.id, {
        feedback: fb,
        inline_comments: getCommentPayload(),
      })
      setRejectFeedback('')
      await refreshBoard()
      onClose()
    } catch (err) {
      setDiffError(diffErrorMessage(err))
    } finally {
      setActionBusy(false)
    }
  }, [projectId, reviewTask, rejectFeedback, refreshBoard, getCommentPayload, onClose])

  if (!reviewTask) {
    return null
  }

  const diffTitle =
    diff?.files_affected?.length && diff.files_affected[0]
      ? diff.files_affected[0]!
      : `Task: ${reviewTask.title}`
  const apiFilePath = (diff?.files_affected?.[0] ?? '').trim()

  return (
    <>
      <div className={styles.backdrop} aria-hidden />
      <aside
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="review-panel-title"
      >
        <div className={styles.panelHeader}>
          <div>
            <h2 id="review-panel-title" className={styles.title}>
              Code review
            </h2>
            <p className={styles.subtitle}>{reviewTask.title}</p>
          </div>
          <div className="flex items-center gap-2">
            {canSaveTemplate ? (
              <Button variant="secondary" onClick={() => setSaveTemplateOpen(true)}>
                Lưu làm template
              </Button>
            ) : null}
            <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close review panel">
              Close
            </button>
          </div>
        </div>

        <div className={styles.statusRow}>
          {diffLoading ? (
            <>
              <Spinner aria-label="Loading diff" />
              <span>Loading diff…</span>
            </>
          ) : null}
        </div>

        {diffError ? (
          <p className={styles.error} role="alert">
            {diffError}
          </p>
        ) : null}

        {/* ── Tab bar ── */}
        <div className={styles.tabs}>
          <button
            type="button"
            className={`${styles.tab} ${reviewTab === 'diff' ? styles.tabActive : ''}`}
            onClick={() => setReviewTab('diff')}
          >
            <Code2 size={14} aria-hidden="true" />
            Diff (coder output)
          </button>
          <button
            type="button"
            className={`${styles.tab} ${reviewTab === 'ai' ? styles.tabActive : ''}`}
            onClick={() => setReviewTab('ai')}
          >
            <Eye size={14} aria-hidden="true" />
            AI Review
            {reviewState.report?.score != null ? (
              <span className={styles.tabBadge}>{reviewState.report.score}</span>
            ) : null}
          </button>
        </div>

        {/* ── Diff tab ── */}
        {reviewTab === 'diff' ? (
          <div className={styles.tabContent}>
            {!diffLoading && diff ? (
              <>
                <DiffViewer
                  original={diff.original_content}
                  modified={diff.modified_content}
                  title={diffTitle}
                  height="55vh"
                  highlightedLine={
                    highlightedLine && highlightedLine.file === apiFilePath
                      ? highlightedLine.line
                      : null
                  }
                  onLineClick={
                    apiFilePath
                      ? (file, line) => {
                          setActiveCommentLine(line)
                          setHighlightedLine({ file, line })
                        }
                      : undefined
                  }
                  onModifiedEditor={setModifiedEditor}
                />
                {apiFilePath && modifiedEditor ? (
                  <InlineCommentOverlay
                    modifiedEditor={modifiedEditor}
                    taskId={reviewTask.id}
                    apiFilePath={apiFilePath}
                    comments={inlineCommentRows}
                    activeLine={activeCommentLine}
                    onCloseComposer={() => setActiveCommentLine(null)}
                    onSaved={refreshInlineComments}
                  />
                ) : null}
              </>
            ) : !diffLoading ? (
              <p className={styles.diffEmpty}>
                No diff available yet — agent may still be running.
              </p>
            ) : null}
          </div>
        ) : null}

        {/* ── AI Review tab ── */}
        {reviewTab === 'ai' ? (
          <div className={styles.tabContent}>
            <AiReviewPanel
              reviewState={reviewState}
              onCommentClick={(file, line) => {
                setHighlightedLine({ file, line })
                if (typeof line === 'number') setActiveCommentLine(line)
                setReviewTab('diff')
              }}
            />
          </div>
        ) : null}

        <div className={styles.actions}>
          <div className={styles.row}>
            <Button variant="primary" disabled={actionBusy || diffLoading || !diff} onClick={() => void onApprove()}>
              ✓ Approve &amp; merge
            </Button>
          </div>

          <div>
            <label htmlFor="review-reject-feedback" className={styles.rejectLabel}>
              Reject with feedback (agent retries)
            </label>
            <p className={styles.rejectHint}>
              Write what needs to change. The coder agent will try again with your feedback.
            </p>
            <textarea
              id="review-reject-feedback"
              className={styles.textarea}
              value={rejectFeedback}
              onChange={(e) => setRejectFeedback(e.target.value)}
              placeholder="Explain what should change before the agent retries…"
              disabled={actionBusy}
            />
          </div>
          <div className={styles.row}>
            <Button
              variant="danger"
              disabled={actionBusy || !rejectFeedback.trim()}
              onClick={() => void onReject()}
            >
              ↩ Reject (retry)
            </Button>
            <Button
              variant="secondary"
              disabled={actionBusy}
              onClick={() => void onPermanentReject()}
              title="Move task to Rejected column permanently — no agent retry"
            >
              🚫 Discard task
            </Button>
          </div>
        </div>
      </aside>

      <SaveAsTemplateModal
        open={saveTemplateOpen}
        projectId={projectId}
        taskTitle={reviewTask.title}
        taskDescription={reviewTask.description}
        onClose={() => setSaveTemplateOpen(false)}
      />
    </>
  )
}
