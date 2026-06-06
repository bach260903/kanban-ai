/**
 * AI Review Panel — shows score, suggestion, test results and inline comments
 * for the current review task (US1 / T036).
 *
 * States:
 *  - null report  → "Đang chờ agent..."
 *  - running      → Spinner
 *  - error        → error message in red
 *  - complete     → ScoreGauge + suggestion chip + test summary + comments grouped by file
 */

import { useMemo } from 'react'

import type { ReviewComment, ReviewReport, ReviewSeverity, ReviewSuggestion } from '../../types'
import type { UseReviewReportResult } from '../../services/review-api'
import { Spinner } from '../atoms/spinner'
import { ScoreGauge } from '../atoms/score-gauge'

// ---------------------------------------------------------------------------
// Sub-components / helpers
// ---------------------------------------------------------------------------

const SEVERITY_ICON: Record<ReviewSeverity, string> = {
  info: 'ℹ️',
  warning: '⚠️',
  error: '🔴',
}

const SUGGESTION_STYLE: Record<ReviewSuggestion, { bg: string; text: string; label: string }> = {
  approve: { bg: 'bg-green-100', text: 'text-green-800', label: 'Approve' },
  needs_changes: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Needs changes' },
}

function SuggestionChip({ suggestion }: { suggestion: ReviewSuggestion }) {
  const style = SUGGESTION_STYLE[suggestion]
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  )
}

function TestResultLine({
  runner,
  pass,
  fail,
  errorOutput,
}: {
  runner: string | null
  pass: number | null
  fail: number | null
  errorOutput?: string | null
}) {
  if (!runner) return <p className="text-xs mt-1 text-gray-400">No test runner detected.</p>
  const p = pass ?? 0
  const f = fail ?? 0
  const label = runner === 'npm_test' ? 'Jest' : 'pytest'
  const color = f > 0 ? 'text-red-600' : 'text-green-700'
  return (
    <div className="mt-1">
      <p className={`text-xs ${color}`}>
        {label}: {p} passed, {f} failed
      </p>
      {f > 0 && errorOutput && (
        <pre className="mt-1 max-h-32 overflow-y-auto text-xs bg-red-50 text-red-700 rounded p-2 whitespace-pre-wrap">
          {errorOutput}
        </pre>
      )}
    </div>
  )
}

function CommentItem({
  comment,
  onCommentClick,
}: {
  comment: ReviewComment
  onCommentClick?: (file: string, line: number | null) => void
}) {
  const icon = SEVERITY_ICON[comment.severity] ?? 'ℹ️'
  const clickable = typeof onCommentClick === 'function'
  return (
    <li
      className={`flex gap-1.5 py-1 text-xs border-b border-gray-100 last:border-0 ${clickable ? 'cursor-pointer hover:bg-gray-50' : ''}`}
      onClick={clickable ? () => onCommentClick(comment.file_path, comment.line_number) : undefined}
    >
      <span className="shrink-0">{icon}</span>
      <span className="text-gray-700 leading-snug">
        {comment.line_number != null && (
          <span className="text-gray-400 mr-1">:{comment.line_number}</span>
        )}
        {comment.content}
      </span>
    </li>
  )
}

function CommentsSection({
  comments,
  onCommentClick,
}: {
  comments: ReviewComment[]
  onCommentClick?: (file: string, line: number | null) => void
}) {
  // Group by file_path
  const byFile = useMemo(() => {
    const groups = new Map<string, ReviewComment[]>()
    for (const c of comments) {
      const key = c.file_path
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(c)
    }
    return groups
  }, [comments])

  if (byFile.size === 0) return null

  return (
    <div className="mt-3">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
        Comments
      </p>
      {Array.from(byFile.entries()).map(([file, items]) => (
        <div key={file} className="mb-2">
          <p className="text-xs font-mono text-gray-500 truncate mb-0.5" title={file}>
            {file}
          </p>
          <ul className="list-none p-0 m-0">
            {items.map((c) => (
              <CommentItem key={c.id} comment={c} onCommentClick={onCommentClick} />
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export type AiReviewPanelProps = {
  /** Report + state from useReviewReport (injected for testability). */
  reviewState: Pick<UseReviewReportResult, 'report' | 'loading' | 'error'>
  /** Called when the user clicks on a comment — scroll DiffViewer to that file/line. */
  onCommentClick?: (file: string, line: number | null) => void
}

/**
 * Sidebar panel showing the AI review result alongside the diff.
 * Fixed width ~380 px, separated from DiffViewer by a left border.
 */
export function AiReviewPanel({ reviewState, onCommentClick }: AiReviewPanelProps) {
  const { report, loading, error } = reviewState

  return (
    <aside
      className="w-[380px] shrink-0 border-l border-gray-200 flex flex-col bg-white overflow-y-auto"
      aria-label="AI review"
    >
      <div className="px-4 py-3 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-gray-800">AI Review</h3>
      </div>

      <div className="px-4 py-3 flex-1">
        {/* No report yet */}
        {!report && !loading && !error && (
          <p className="text-sm text-gray-400">Đang chờ agent...</p>
        )}

        {/* Initial loading */}
        {loading && !report && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Spinner aria-label="Loading review" />
            <span>Loading…</span>
          </div>
        )}

        {/* Unexpected fetch error */}
        {error && (
          <p className="text-sm text-red-600" role="alert">{error}</p>
        )}

        {report && (
          <>
            {/* running state */}
            {report.status === 'running' && (
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <Spinner aria-label="Review running" />
                <span>Review đang chạy…</span>
              </div>
            )}

            {/* pending state */}
            {report.status === 'pending' && (
              <p className="text-sm text-gray-400">Đang chờ agent...</p>
            )}

            {/* error state */}
            {report.status === 'error' && (
              <div>
                <p className="text-sm font-semibold text-red-600 mb-1">Review thất bại</p>
                {report.error_message && (
                  <pre className="text-xs text-red-500 whitespace-pre-wrap bg-red-50 rounded p-2">
                    {report.error_message}
                  </pre>
                )}
              </div>
            )}

            {/* complete state */}
            {report.status === 'complete' && (
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <ScoreGauge score={report.score ?? 0} />
                  {report.suggestion && <SuggestionChip suggestion={report.suggestion} />}
                </div>
                <TestResultLine
                  runner={report.test_runner}
                  pass={report.test_pass}
                  fail={report.test_fail}
                  errorOutput={(report as any).test_error}
                />
                <CommentsSection
                  comments={report.comments}
                  onCommentClick={onCommentClick}
                />
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  )
}
