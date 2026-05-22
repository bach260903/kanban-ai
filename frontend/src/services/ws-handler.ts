/**
 * WebSocket event router for review-related stream events (US1 / T038).
 *
 * The backend reviewer_node publishes three event types over the task thought-stream:
 *   - REVIEW_SCORE   — overall score + suggestion + test counts
 *   - REVIEW_COMMENT — list of inline comments
 *   - REVIEW_ERROR   — error_message when reviewer fails
 *
 * This module provides `handleReviewStreamEvent`, a pure handler that can be
 * plugged into any event consumer (e.g. `useThoughtStream` subscribers or
 * `useReviewReport.applyStreamEvent`).
 */

import type { UseReviewReportResult } from './review-api'

/** Event types pushed by the backend reviewer_node. */
export const REVIEW_EVENT_TYPES = ['REVIEW_SCORE', 'REVIEW_COMMENT', 'REVIEW_ERROR'] as const

export type ReviewEventType = (typeof REVIEW_EVENT_TYPES)[number]

/**
 * Returns `true` when the message is a review-related event that should
 * be forwarded to `useReviewReport.applyStreamEvent`.
 */
export function isReviewEvent(msg: Record<string, unknown>): boolean {
  return REVIEW_EVENT_TYPES.includes(msg.type as ReviewEventType)
}

/**
 * Forward a WebSocket message to the review report state if it is a
 * review event (REVIEW_SCORE / REVIEW_COMMENT / REVIEW_ERROR).
 *
 * Usage:
 * ```ts
 * const reviewState = useReviewReport(taskId)
 * // inside useThoughtStream subscriber:
 * handleReviewStreamEvent(event, reviewState.applyStreamEvent)
 * ```
 */
export function handleReviewStreamEvent(
  msg: Record<string, unknown>,
  applyStreamEvent: UseReviewReportResult['applyStreamEvent'],
): void {
  if (isReviewEvent(msg)) {
    applyStreamEvent(msg)
  }
}
