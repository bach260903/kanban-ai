/**
 * Review API client + useReviewReport polling hook (US1 / T034).
 *
 * - reviewApi(token) — plain fetch helper
 * - useReviewReport(taskId) — auto-polls while status is "pending"|"running", stops on terminal states
 */

import { isAxiosError } from 'axios'
import { useCallback, useEffect, useRef, useState } from 'react'

import type { ReviewReport } from '../types'
import { createApiClient } from './api-client'
import { getAuthToken } from './api'

const REVIEW_POLL_INTERVAL_MS = 4_000

/** Fetch the latest AI review report for a task. Throws AxiosError on failure. */
export function reviewApi(token: string | null) {
  const client = createApiClient(token)
  return {
    async getReport(taskId: string): Promise<ReviewReport> {
      const { data } = await client.get<ReviewReport>(`/tasks/${taskId}/review`)
      return data
    },
  }
}

/** Shape returned by {@link useReviewReport}. */
export type UseReviewReportResult = {
  report: ReviewReport | null
  /** True while the initial fetch or a poll is in flight. */
  loading: boolean
  /** Non-null only on unexpected errors (404 is silently treated as "no report yet"). */
  error: string | null
  /** Apply a REVIEW_SCORE / REVIEW_COMMENT / REVIEW_ERROR event from the WS stream. */
  applyStreamEvent: (event: Record<string, unknown>) => void
}

/**
 * Fetch and poll the AI review report for a task.
 *
 * - Fetches immediately on mount (or when taskId changes).
 * - Polls every 2 s while status is "pending" | "running".
 * - Stops polling automatically when status becomes "complete" | "error".
 * - 404 is handled silently (report not created yet).
 */
export function useReviewReport(taskId: string | null): UseReviewReportResult {
  const [report, setReport] = useState<ReviewReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const mountedRef = useRef(true)

  const clearPoll = useCallback(() => {
    if (intervalRef.current != null) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  const normalizeComments = useCallback((raw: unknown): ReviewReport['comments'] => {
    if (!Array.isArray(raw)) return []
    return raw
      .map((row, idx) => {
        if (typeof row !== 'object' || row == null) return null
        const item = row as Record<string, unknown>
        const filePath = typeof item.file_path === 'string' ? item.file_path : 'unknown'
        const lineNumber = typeof item.line_number === 'number' ? item.line_number : null
        const content = typeof item.content === 'string' ? item.content : ''
        const severity =
          item.severity === 'error' || item.severity === 'warning' || item.severity === 'info'
            ? item.severity
            : 'info'
        const id =
          typeof item.id === 'string' && item.id.length > 0
            ? item.id
            : `${filePath}:${lineNumber ?? 'null'}:${idx}:${content.slice(0, 32)}`
        return {
          id,
          file_path: filePath,
          line_number: lineNumber,
          content,
          severity,
        }
      })
      .filter((v): v is ReviewReport['comments'][number] => v != null)
  }, [])

  const fetchReport = useCallback(async () => {
    if (!taskId) return
    const token = getAuthToken()
    try {
      const api = reviewApi(token)
      const data = await api.getReport(taskId)
      if (!mountedRef.current) return
      setReport(data)
      setError(null)
    } catch (err) {
      if (!mountedRef.current) return
      // 404 = no report yet — silent
      if (isAxiosError(err) && err.response?.status === 404) {
        setReport((prev) => {
          if (prev != null) return prev
          return {
            id: '',
            task_id: taskId,
            status: 'pending',
            score: null,
            suggestion: null,
            test_runner: null,
            test_pass: null,
            test_fail: null,
            comments: [],
            error_message: null,
            created_at: new Date().toISOString(),
            completed_at: null,
          }
        })
        setError(null)
        return
      }
      const msg =
        isAxiosError(err) && typeof err.response?.data?.detail === 'string'
          ? err.response.data.detail
          : err instanceof Error
            ? err.message
            : 'Failed to load review report'
      setError(msg)
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [taskId])

  useEffect(() => {
    mountedRef.current = true
    if (!taskId) {
      setReport(null)
      setError(null)
      setLoading(false)
      clearPoll()
      return
    }

    setLoading(true)
    setReport(null)
    setError(null)
    void fetchReport()

    return () => {
      mountedRef.current = false
      clearPoll()
    }
  }, [taskId, clearPoll, fetchReport])

  useEffect(() => {
    if (!taskId) {
      clearPoll()
      return
    }
    const status = report?.status
    const shouldPoll = status === 'pending' || status === 'running'
    if (!shouldPoll) {
      clearPoll()
      return
    }
    if (intervalRef.current != null) {
      return
    }
    intervalRef.current = setInterval(() => {
      void fetchReport()
    }, REVIEW_POLL_INTERVAL_MS)
    return () => {
      clearPoll()
    }
  }, [taskId, report?.status, fetchReport, clearPoll])

  /**
   * Apply a REVIEW_SCORE / REVIEW_COMMENT / REVIEW_ERROR event pushed via WebSocket
   * so the UI updates immediately without waiting for the next poll.
   */
  const applyStreamEvent = useCallback((event: Record<string, unknown>) => {
    const type = event.type as string | undefined
    if (!type) return

    setReport((prev) => {
      if (type === 'REVIEW_SCORE') {
        const base: ReviewReport = prev ?? {
          id: String(event.report_id ?? ''),
          task_id: String(event.task_id ?? ''),
          status: 'complete',
          score: null,
          suggestion: null,
          test_runner: null,
          test_pass: null,
          test_fail: null,
          comments: [],
          error_message: null,
          created_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
        }
        return {
          ...base,
          status: 'complete',
          score: typeof event.score === 'number' ? event.score : base.score,
          suggestion: (event.suggestion as ReviewReport['suggestion']) ?? base.suggestion,
          test_pass: typeof event.test_pass === 'number' ? event.test_pass : base.test_pass,
          test_fail: typeof event.test_fail === 'number' ? event.test_fail : base.test_fail,
          test_runner: typeof event.test_runner === 'string' ? event.test_runner : base.test_runner,
        }
      }

      if (type === 'REVIEW_COMMENT') {
        const base: ReviewReport = prev ?? {
          id: String(event.report_id ?? ''),
          task_id: String(event.task_id ?? ''),
          status: 'running',
          score: null,
          suggestion: null,
          test_runner: null,
          test_pass: null,
          test_fail: null,
          comments: [],
          error_message: null,
          created_at: new Date().toISOString(),
          completed_at: null,
        }
        return { ...base, comments: normalizeComments(event.comments) }
      }

      if (type === 'REVIEW_ERROR') {
        const base: ReviewReport = prev ?? {
          id: String(event.report_id ?? ''),
          task_id: String(event.task_id ?? ''),
          status: 'error',
          score: null,
          suggestion: null,
          test_runner: null,
          test_pass: null,
          test_fail: null,
          comments: [],
          error_message: null,
          created_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
        }
        return {
          ...base,
          status: 'error',
          error_message: typeof event.error === 'string' ? event.error : null,
        }
      }

      return prev
    })

    // Stop polling on terminal WS events
    if (type === 'REVIEW_SCORE' || type === 'REVIEW_ERROR') {
      clearPoll()
    }
  }, [clearPoll, normalizeComments])

  return { report, loading, error, applyStreamEvent }
}
