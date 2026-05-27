import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { memo, useMemo, type KeyboardEvent, type MouseEvent } from 'react'

import { Avatar } from '../atoms/avatar'
import { AssignMember } from '../molecules/assign-member'
import { DependencyBadge } from '../molecules/dependency-badge'
import type { TaskColumnItem } from '../../store/task-store'
import type { AgentRunStatus, ProjectMember, ProjectRole, TaskStatus } from '../../types'
import { stripMarkdown } from '../../utils/strip-markdown'

export type TaskCardData = TaskColumnItem & {
  dependsOnCount?: number
  blockedByTitles?: string[]
  aiRunStatus?: AgentRunStatus | null
}

export type TaskCardProps = {
  task: TaskCardData
  sortableDisabled?: boolean
  isAgentRunning?: boolean
  isReviewSelected?: boolean
  members?: ProjectMember[]
  currentUserRole?: ProjectRole
  onAssignUser?: (userId: string | null) => void
  onView?: () => void
  onReject?: () => void
  onStart?: () => void
  onCancel?: () => void
  startBusy?: boolean
  cancelBusy?: boolean
  onSaveAsTemplate?: () => void
}

function canAssign(role: ProjectRole | undefined): boolean {
  return role === 'owner' || role === 'leader'
}

const STATUS_TONE: Record<
  TaskStatus,
  { ring: string; chip: string; chipText: string; label: string }
> = {
  todo: {
    ring: 'ring-slate-200',
    chip: 'bg-slate-100',
    chipText: 'text-slate-700',
    label: 'To do',
  },
  in_progress: {
    ring: 'ring-brand-200',
    chip: 'bg-brand-50',
    chipText: 'text-brand-700',
    label: 'In progress',
  },
  review: {
    ring: 'ring-violet-200',
    chip: 'bg-violet-50',
    chipText: 'text-violet-700',
    label: 'Review',
  },
  done: {
    ring: 'ring-emerald-200',
    chip: 'bg-emerald-50',
    chipText: 'text-emerald-700',
    label: 'Done',
  },
  rejected: {
    ring: 'ring-red-200',
    chip: 'bg-red-50',
    chipText: 'text-red-700',
    label: 'Rejected',
  },
  conflict: {
    ring: 'ring-amber-300',
    chip: 'bg-amber-50',
    chipText: 'text-amber-700',
    label: 'Conflict',
  },
}

const AI_STATUS_TONE: Record<
  AgentRunStatus,
  { dot: string; chip: string; label: string }
> = {
  running: { dot: 'bg-brand-500 animate-pulse', chip: 'bg-brand-50 text-brand-700', label: 'AI running' },
  success: { dot: 'bg-emerald-500', chip: 'bg-emerald-50 text-emerald-700', label: 'AI done' },
  failure: { dot: 'bg-red-500', chip: 'bg-red-50 text-red-700', label: 'AI failed' },
  awaiting_hil: { dot: 'bg-violet-500', chip: 'bg-violet-50 text-violet-700', label: 'Awaiting review' },
  paused: { dot: 'bg-amber-500', chip: 'bg-amber-50 text-amber-800', label: 'AI paused' },
  timeout: { dot: 'bg-red-500', chip: 'bg-red-50 text-red-700', label: 'AI timeout' },
}

function PriorityIndicator({ value }: { value: number }) {
  const tone =
    value <= 1
      ? { bar: 'bg-red-500', text: 'text-red-700', label: 'High' }
      : value <= 3
        ? { bar: 'bg-cta', text: 'text-cta-hover', label: 'Medium' }
        : { bar: 'bg-slate-400', text: 'text-slate-600', label: 'Low' }
  return (
    <span
      className="inline-flex items-center gap-1 font-mono text-[11px] font-semibold uppercase tracking-wide"
      title={`Priority ${value} (${tone.label})`}
    >
      <span aria-hidden className={`block h-3 w-1 rounded-sm ${tone.bar}`} />
      <span className={tone.text}>P{value}</span>
    </span>
  )
}

function IconEye() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden>
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function IconXCircle() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <path d="m15 9-6 6M9 9l6 6" />
    </svg>
  )
}

function IconPlay() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5" aria-hidden>
      <path d="M8 5v14l11-7z" />
    </svg>
  )
}

function IconLink() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5" aria-hidden>
      <path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.72-1.71" />
    </svg>
  )
}

function IconLock() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5" aria-hidden>
      <rect x="3" y="11" width="18" height="11" rx="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  )
}

function IconBookmark() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden>
      <path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function IconGripDots() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden>
      <circle cx="9" cy="6" r="1.5" />
      <circle cx="15" cy="6" r="1.5" />
      <circle cx="9" cy="12" r="1.5" />
      <circle cx="15" cy="12" r="1.5" />
      <circle cx="9" cy="18" r="1.5" />
      <circle cx="15" cy="18" r="1.5" />
    </svg>
  )
}

function HoverActionButton({
  label,
  tone,
  onClick,
  children,
  disabled,
}: {
  label: string
  tone: 'neutral' | 'brand' | 'danger'
  onClick: () => void
  children: React.ReactNode
  disabled?: boolean
}) {
  const toneClass =
    tone === 'brand'
      ? 'text-brand-700 hover:bg-brand-50 focus-visible:ring-brand-300'
      : tone === 'danger'
        ? 'text-red-700 hover:bg-red-50 focus-visible:ring-red-300'
        : 'text-slate-700 hover:bg-slate-100 focus-visible:ring-slate-300'

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(e: MouseEvent<HTMLButtonElement>) => {
        e.stopPropagation()
        onClick()
      }}
      className={`inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-md transition-colors duration-150 focus:outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-40 ${toneClass}`}
    >
      {children}
    </button>
  )
}

function TaskCardInner({
  task,
  sortableDisabled = true,
  isAgentRunning = false,
  isReviewSelected = false,
  members = [],
  currentUserRole,
  onAssignUser,
  onView,
  onReject,
  onStart,
  onCancel,
  startBusy = false,
  cancelBusy = false,
  onSaveAsTemplate,
}: TaskCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: task.id,
    disabled: sortableDisabled || task.is_blocked,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const statusTone = STATUS_TONE[task.status]
  const aiTone = task.aiRunStatus ? AI_STATUS_TONE[task.aiRunStatus] : null
  const blocked = Boolean(task.is_blocked)
  const dependsOn = task.dependsOnCount ?? 0
  const blockedByTitles = task.blockedByTitles ?? []
  const draggable = !sortableDisabled && !blocked
  const assignee = members.find((m) => m.user_id === task.assigned_to) ?? null
  const showAssignUi = canAssign(currentUserRole) && onAssignUser && members.length > 0
  const descriptionPreview = useMemo(
    () => stripMarkdown(task.description),
    [task.description],
  )

  const handleCardClick = (e: MouseEvent<HTMLElement>) => {
    if (!onView) return
    if ((e.target as HTMLElement).closest('button, [data-no-dnd]')) return
    onView()
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    if (!onView) return
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onView()
    }
  }

  const dragHandlers = draggable ? { ...attributes, ...listeners } : {}

  return (
    <article
      ref={setNodeRef}
      style={style}
      {...dragHandlers}
      onClick={handleCardClick}
      onKeyDown={handleKeyDown}
      role={onView ? 'button' : 'article'}
      tabIndex={onView ? 0 : undefined}
      aria-label={`Task ${task.title}`}
      data-status={task.status}
      className={[
        'group relative flex w-full select-none flex-col gap-2 rounded-xl bg-white p-3 text-left shadow-elev-1 ring-1 transition-all duration-200',
        statusTone.ring,
        isDragging ? 'rotate-1 scale-[1.02] shadow-elev-3 ring-brand-400 opacity-90' : '',
        isAgentRunning ? 'animate-pulse-brand ring-2 ring-brand-400' : '',
        task.status === 'conflict' ? 'ring-2 ring-amber-400' : '',
        isReviewSelected ? 'ring-2 ring-violet-400 shadow-ring-brand' : '',
        onView ? 'cursor-pointer hover:-translate-y-0.5 hover:shadow-elev-2' : '',
        draggable ? 'cursor-grab active:cursor-grabbing' : '',
        blocked ? 'opacity-60 cursor-not-allowed' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {/* Blocked badge */}
      {blocked ? (
        <div className="absolute inset-x-0 top-0 flex items-center gap-1 rounded-t-xl px-2 py-1">
          <DependencyBadge
            blockedByTitles={blockedByTitles}
            forceCount={blockedByTitles.length || dependsOn || 1}
          />
        </div>
      ) : null}

      {/* Top row: priority + status badge + drag handle */}
      <div className={`flex items-start justify-between gap-2 ${blocked ? 'mt-5' : ''}`}>
        <div className="flex items-center gap-2">
          <PriorityIndicator value={task.priority} />
          <span
            className={`inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider ${statusTone.chip} ${statusTone.chipText}`}
          >
            {statusTone.label}
          </span>
        </div>
        {draggable ? (
          <span
            aria-hidden
            title="Drag to move"
            className="text-slate-300 opacity-0 transition-opacity duration-150 group-hover:opacity-100"
          >
            <IconGripDots />
          </span>
        ) : null}
      </div>

      {/* Title */}
      <h4 className="line-clamp-2 font-sans text-[14px] font-semibold leading-snug text-slate-900">
        {task.title}
      </h4>

      {/* Description preview (markdown stripped to plain text) */}
      {descriptionPreview ? (
        <p className="line-clamp-2 text-[12.5px] leading-relaxed text-slate-600">
          {descriptionPreview}
        </p>
      ) : null}

      {/* AI status band */}
      {aiTone ? (
        <div
          role="status"
          aria-label={aiTone.label}
          className={`inline-flex items-center gap-1.5 self-start rounded-md px-2 py-1 font-mono text-[10.5px] font-semibold uppercase tracking-wide ${aiTone.chip}`}
        >
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${aiTone.dot}`} />
          {aiTone.label}
        </div>
      ) : null}

      {/* Footer: assignee + dependency + actions */}
      <div className="mt-1 flex items-center justify-between gap-2 border-t border-slate-100 pt-2">
        <div className="flex items-center gap-2">
          {showAssignUi ? (
            <AssignMember
              members={members}
              currentAssigneeId={task.assigned_to}
              onAssign={onAssignUser}
            />
          ) : assignee ? (
            <span
              className="flex items-center gap-1.5"
              title={`Assigned to ${assignee.display_name}`}
            >
              <Avatar name={assignee.display_name} size="sm" />
              <span className="font-mono text-[11px] font-medium text-slate-600">
                {assignee.display_name.split(' ')[0]}
              </span>
            </span>
          ) : (
            <span
              className="inline-flex items-center gap-1 font-mono text-[11px] text-slate-400"
              title="Unassigned"
            >
              <span
                aria-hidden
                className="grid h-6 w-6 place-items-center rounded-full border border-dashed border-slate-300 text-slate-400"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 21a8 8 0 0 1 16 0" strokeLinecap="round" />
                </svg>
              </span>
              Unassigned
            </span>
          )}

          {dependsOn > 0 ? (
            <span
              className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[10.5px] font-semibold ${
                blocked ? 'bg-amber-50 text-amber-800' : 'bg-slate-100 text-slate-600'
              }`}
              title={`${dependsOn} dependenc${dependsOn === 1 ? 'y' : 'ies'}`}
            >
              <IconLink />
              {dependsOn}
            </span>
          ) : null}
        </div>

        {/* Hover-reveal actions */}
        <div className="flex items-center gap-0.5 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100">
          {onView ? (
            <HoverActionButton label="View task" tone="neutral" onClick={onView}>
              <IconEye />
            </HoverActionButton>
          ) : null}
          {onReject ? (
            <HoverActionButton label="Reject" tone="danger" onClick={onReject}>
              <IconXCircle />
            </HoverActionButton>
          ) : null}
          {onSaveAsTemplate ? (
            <HoverActionButton label="Lưu làm template" tone="neutral" onClick={onSaveAsTemplate}>
              <IconBookmark />
            </HoverActionButton>
          ) : null}
        </div>
      </div>

      {/* Persistent action buttons (Start / Cancel) */}
      {(onStart || onCancel) && (
        <div className="flex items-center justify-end gap-2">
          {onCancel ? (
            <button
              type="button"
              disabled={cancelBusy}
              onClick={(e) => {
                e.stopPropagation()
                onCancel()
              }}
              className="inline-flex h-7 cursor-pointer items-center gap-1 rounded-md border border-red-200 bg-white px-2 font-mono text-[11px] font-semibold text-red-700 transition-colors duration-150 hover:bg-red-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-300 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {cancelBusy ? 'Cancelling…' : 'Cancel'}
            </button>
          ) : null}
          {onStart && !blocked ? (
            <button
              type="button"
              disabled={startBusy}
              onClick={(e) => {
                e.stopPropagation()
                onStart()
              }}
              className="inline-flex h-7 cursor-pointer items-center gap-1 rounded-md bg-cta px-2.5 font-mono text-[11px] font-semibold text-white shadow-elev-1 transition-all duration-150 hover:bg-cta-hover hover:shadow-elev-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-cta disabled:cursor-not-allowed disabled:opacity-50"
            >
              <IconPlay />
              {startBusy ? 'Starting…' : 'Start'}
            </button>
          ) : null}
        </div>
      )}
    </article>
  )
}

export const TaskCard = memo(TaskCardInner)
