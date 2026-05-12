import type { AgentRunStatus, DocumentStatus, TaskStatus } from '../../types'

import styles from './badge.module.css'

export type BadgeKind = 'task' | 'document' | 'agent'

export type BadgeProps = {
  kind: BadgeKind
  status: TaskStatus | DocumentStatus | AgentRunStatus
  /** Overrides default label derived from `status` */
  label?: string
  className?: string
}

const TASK_TONE: Record<TaskStatus, keyof typeof styles> = {
  todo: 'neutral',
  in_progress: 'progress',
  review: 'review',
  done: 'success',
  rejected: 'danger',
  conflict: 'warn',
}

const DOCUMENT_TONE: Record<DocumentStatus, keyof typeof styles> = {
  draft: 'neutral',
  approved: 'success',
  revision_requested: 'warn',
}

const AGENT_TONE: Record<AgentRunStatus, keyof typeof styles> = {
  running: 'progress',
  success: 'success',
  failure: 'danger',
  awaiting_hil: 'review',
  paused: 'neutral',
}

function toneFor(kind: BadgeKind, status: BadgeProps['status']): keyof typeof styles {
  if (kind === 'task') {
    return TASK_TONE[status as TaskStatus] ?? 'neutral'
  }
  if (kind === 'document') {
    return DOCUMENT_TONE[status as DocumentStatus] ?? 'neutral'
  }
  return AGENT_TONE[status as AgentRunStatus] ?? 'neutral'
}

function defaultLabel(status: string): string {
  return status.replace(/_/g, ' ')
}

export function Badge({ kind, status, label, className }: BadgeProps) {
  const tone = toneFor(kind, status)
  const text = label ?? defaultLabel(status)
  const merged = [styles.badge, styles[tone], className].filter(Boolean).join(' ')
  return <span className={merged}>{text}</span>
}
