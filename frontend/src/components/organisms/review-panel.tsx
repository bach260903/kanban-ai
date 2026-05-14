import { isAxiosError } from 'axios'
import type { editor } from 'monaco-editor'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { Button } from '../atoms/button'
import { Spinner } from '../atoms/spinner'
import { DiffViewer } from '../molecules/diff-viewer'
import { InlineCommentOverlay } from '../molecules/inline-comment-overlay'
import {
  approveTask,
  getDiff,
  getTaskComments,
  getTasks,
  groupedResponseToTaskColumns,
  rejectTask,
} from '../../services/task-api'
import type { InlineCommentItem, TaskDiffResponse } from '../../services/task-api'
import { useTaskStore } from '../../store/task-store'

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
}

/**
 * Code review HIL when a task is in ``review`` (US9 / T066): diff + approve / reject.
 */
export function ReviewPanel({ projectId }: ReviewPanelProps) {
  const columns = useTaskStore((s) => s.columns)
  const setColumns = useTaskStore((s) => s.setColumns)

  const reviewTask = useMemo(() => {
    const list = [...columns.review].sort((a, b) => a.priority - b.priority || a.title.localeCompare(b.title))
    return list[0]
  }, [columns.review])

  const [diff, setDiff] = useState<TaskDiffResponse | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)
  const [diffError, setDiffError] = useState<string | null>(null)
  const [actionBusy, setActionBusy] = useState(false)
  const [rejectFeedback, setRejectFeedback] = useState('')
  const [modifiedEditor, setModifiedEditor] = useState<editor.IStandaloneCodeEditor | null>(null)
  const [inlineComments, setInlineComments] = useState<InlineCommentItem[]>([])
  const [activeCommentLine, setActiveCommentLine] = useState<number | null>(null)

  const refreshBoard = useCallback(async () => {
    const data = await getTasks(projectId)
    setColumns(groupedResponseToTaskColumns(data))
  }, [projectId, setColumns])

  const refreshInlineComments = useCallback(async () => {
    const tid = reviewTask?.id
    if (!tid) return
    try {
      const rows = await getTaskComments(tid)
      setInlineComments(rows)
    } catch {
      setInlineComments([])
    }
  }, [reviewTask?.id])

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
      setInlineComments([])
      return
    }
    void refreshInlineComments()
  }, [reviewTask?.id, diff?.id, refreshInlineComments])

  useEffect(() => {
    setActiveCommentLine(null)
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
    } catch (err) {
      setDiffError(diffErrorMessage(err))
    } finally {
      setActionBusy(false)
    }
  }, [projectId, reviewTask, refreshBoard])

  const onReject = useCallback(async () => {
    if (!reviewTask) return
    const fb = rejectFeedback.trim()
    if (!fb) return
    setActionBusy(true)
    setDiffError(null)
    try {
      await rejectTask(projectId, reviewTask.id, fb)
      setRejectFeedback('')
      await refreshBoard()
    } catch (err) {
      setDiffError(diffErrorMessage(err))
    } finally {
      setActionBusy(false)
    }
  }, [projectId, reviewTask, rejectFeedback, refreshBoard])

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
        <h2 id="review-panel-title" className={styles.title}>
          Code review
        </h2>
        <p className={styles.subtitle}>{reviewTask.title}</p>

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

        {!diffLoading && diff ? (
          <>
            <DiffViewer
              original={diff.original_content}
              modified={diff.modified_content}
              title={diffTitle}
              height="42vh"
              onLineClick={apiFilePath ? (_file, line) => setActiveCommentLine(line) : undefined}
              onModifiedEditor={setModifiedEditor}
            />
            {apiFilePath && modifiedEditor ? (
              <InlineCommentOverlay
                modifiedEditor={modifiedEditor}
                taskId={reviewTask.id}
                apiFilePath={apiFilePath}
                comments={inlineComments}
                activeLine={activeCommentLine}
                onCloseComposer={() => setActiveCommentLine(null)}
                onSaved={refreshInlineComments}
              />
            ) : null}
          </>
        ) : null}

        <div className={styles.actions}>
          <div className={styles.row}>
            <Button variant="primary" disabled={actionBusy || diffLoading || !diff} onClick={() => void onApprove()}>
              Approve
            </Button>
          </div>
          <div>
            <label htmlFor="review-reject-feedback" className={styles.rejectLabel}>
              Reject with feedback
            </label>
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
              Reject
            </Button>
          </div>
        </div>
      </aside>
    </>
  )
}
