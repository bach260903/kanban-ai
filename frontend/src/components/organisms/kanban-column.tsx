import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { useMemo, type ReactNode } from 'react'
import { useShallow } from 'zustand/react/shallow'

import { TaskCard, type TaskCardData } from './task-card'
import { useTaskStore } from '../../store/task-store'
import type { AgentRunStatus, ProjectMember, ProjectRole, TaskStatus } from '../../types'

export type KanbanColumnModel = {
  status: TaskStatus
  tasks: TaskCardData[]
}

export type KanbanColumnProps = {
  column: KanbanColumnModel
  taskCardSortableDisabled?: boolean
  isWipColumn?: boolean
  wipLimit?: number
  multiUserWip?: boolean
  currentUserId?: string
  planApproved?: boolean
  onAddTask?: () => void
  onStartTask?: (taskId: string) => void
  startingTaskId?: string | null
  selectedReviewTaskId?: string | null
  onOpenReview?: (taskId: string) => void
  onCancelTask?: (taskId: string) => void
  cancellingTaskId?: string | null
  members?: ProjectMember[]
  currentUserRole?: ProjectRole
  onAssignUser?: (taskId: string, userId: string | null) => void
  onRejectTask?: (taskId: string) => void
  onSaveAsTemplate?: (task: TaskCardData) => void
}

type StatusTheme = {
  title: string
  description: string
  headerBar: string
  chipBg: string
  chipText: string
  dropOver: string
}

const STATUS_THEME: Record<TaskStatus, StatusTheme> = {
  todo: {
    title: 'To do',
    description: 'Tasks waiting to be started.',
    headerBar: 'bg-slate-400',
    chipBg: 'bg-slate-100',
    chipText: 'text-slate-700',
    dropOver: 'ring-slate-400 bg-slate-50/70',
  },
  in_progress: {
    title: 'In progress',
    description: 'Currently being worked on.',
    headerBar: 'bg-brand-600',
    chipBg: 'bg-brand-50',
    chipText: 'text-brand-700',
    dropOver: 'ring-brand-500 bg-brand-50/70',
  },
  review: {
    title: 'Review',
    description: 'Waiting for human review.',
    headerBar: 'bg-violet-500',
    chipBg: 'bg-violet-50',
    chipText: 'text-violet-700',
    dropOver: 'ring-violet-400 bg-violet-50/70',
  },
  done: {
    title: 'Done',
    description: 'Completed and approved.',
    headerBar: 'bg-emerald-500',
    chipBg: 'bg-emerald-50',
    chipText: 'text-emerald-700',
    dropOver: 'ring-emerald-400 bg-emerald-50/70',
  },
}

const EMPTY_HINTS: Record<TaskStatus, string> = {
  todo: 'No tasks yet — add one to get started.',
  in_progress: 'Drag a task here to start the Coder Agent.',
  review: 'Nothing in review yet.',
  done: 'No tasks done yet.',
}

function IconPlus() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden>
      <path d="M12 5v14M5 12h14" />
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

function IconHourglass() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden>
      <path d="M5 22h14M5 2h14M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22M17 2v4.172a2 2 0 0 1-.586 1.414L12 12 7.586 7.586A2 2 0 0 1 7 6.172V2" />
    </svg>
  )
}

function EmptyState({ status, planApproved }: { status: TaskStatus; planApproved: boolean }) {
  if (status === 'todo' && !planApproved) {
    return (
      <div
        role="status"
        className="flex items-start gap-2 rounded-lg border border-dashed border-amber-300 bg-amber-50/70 p-3 text-[12.5px] leading-relaxed text-amber-800"
      >
        <span className="mt-0.5 text-amber-600">
          <IconHourglass />
        </span>
        <span>
          <strong className="font-semibold">Approve PLAN.md</strong> to generate tasks here.
        </span>
      </div>
    )
  }
  return (
    <p className="px-2 py-6 text-center font-sans text-[12px] leading-snug text-slate-500">
      {EMPTY_HINTS[status]}
    </p>
  )
}

function WIPLockBlock(): ReactNode {
  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-xl bg-white/55 backdrop-blur-[1px]">
      <div className="pointer-events-auto flex max-w-[220px] flex-col items-center gap-1.5 rounded-lg border border-brand-200 bg-white px-3 py-2 text-center shadow-elev-2">
        <span className="grid h-7 w-7 place-items-center rounded-full bg-brand-50 text-brand-700">
          <IconLock />
        </span>
        <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-brand-700">
          WIP limit reached
        </p>
        <p className="text-[11px] leading-snug text-slate-500">
          Finish or cancel the current task before starting another.
        </p>
      </div>
    </div>
  )
}

export function KanbanColumn({
  column,
  taskCardSortableDisabled = true,
  isWipColumn = false,
  wipLimit = 1,
  multiUserWip = false,
  currentUserId,
  planApproved = false,
  onAddTask,
  onStartTask,
  startingTaskId = null,
  selectedReviewTaskId = null,
  onOpenReview,
  onCancelTask,
  cancellingTaskId = null,
  members = [],
  currentUserRole,
  onAssignUser,
  onRejectTask,
  onSaveAsTemplate,
}: KanbanColumnProps) {
  const { status, tasks } = column
  const theme = STATUS_THEME[status]
  const ids = tasks.map((t) => t.id)

  // Only subscribe to agent runs for tasks in THIS column, with shallow equality.
  // Without this, ALL 4 columns re-render every time any task's agent status changes.
  const taskIds = useMemo(() => tasks.map((t) => t.id), [tasks])
  const agentMap = useTaskStore(
    useShallow((s) => {
      const result: Record<string, { runId: string; status: AgentRunStatus }> = {}
      for (const id of taskIds) {
        const meta = s.taskAgentByTaskId[id]
        if (meta) result[id] = meta
      }
      return result
    })
  )

  const { setNodeRef, isOver } = useDroppable({
    id: `droppable-${status}`,
    data: { type: 'column', status },
  })

  const isLocked =
    isWipColumn &&
    !multiUserWip &&
    tasks.length >= wipLimit
  const userInProgressCount = multiUserWip
    ? tasks.filter((t) => t.assigned_to === currentUserId).length
    : tasks.length
  const count = tasks.length

  return (
    <section
      aria-labelledby={`kanban-col-${status}`}
      className="flex h-full w-[300px] flex-shrink-0 flex-col rounded-2xl bg-slate-50/80 shadow-elev-1 ring-1 ring-slate-200/70 [scroll-snap-align:start] lg:w-[320px]"
    >
      {/* Column header */}
      <header className="flex items-center justify-between gap-2 rounded-t-2xl border-b border-slate-200/60 bg-white/70 px-3 py-2.5 backdrop-blur-sm">
        <div className="flex min-w-0 items-center gap-2">
          <span aria-hidden className={`h-2 w-2 flex-shrink-0 rounded-full ${theme.headerBar}`} />
          <h3
            id={`kanban-col-${status}`}
            className="truncate font-mono text-[12.5px] font-semibold uppercase tracking-wider text-slate-800"
          >
            {theme.title}
          </h3>
          <span
            className={`inline-flex h-5 min-w-[20px] items-center justify-center rounded-full px-1.5 font-mono text-[10.5px] font-bold ${theme.chipBg} ${theme.chipText}`}
            aria-label={`${count} ${count === 1 ? 'task' : 'tasks'}`}
          >
            {count}
          </span>
        </div>

        {isWipColumn ? (
          <span
            className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ${
              !multiUserWip && isLocked
                ? 'bg-red-50 text-red-700 ring-1 ring-red-200'
                : 'bg-brand-50 text-brand-700 ring-1 ring-brand-200'
            }`}
            title={multiUserWip ? 'Work-in-Progress limit: 1 per developer' : `Work-in-Progress limit: ${wipLimit}`}
          >
            {!multiUserWip && isLocked ? <IconLock /> : null}
            {multiUserWip ? `WIP ${userInProgressCount}/1 you` : `WIP ${count}/${wipLimit}`}
          </span>
        ) : null}
      </header>

      {/* Drop zone */}
      <div
        ref={setNodeRef}
        className={[
          'relative flex flex-1 flex-col gap-2 overflow-y-auto p-2 transition-colors duration-150',
          isOver ? `rounded-b-2xl ring-2 ring-inset ${theme.dropOver}` : '',
          isLocked && isOver ? 'ring-2 ring-inset ring-red-400 bg-red-50/40' : '',
        ]
          .filter(Boolean)
          .join(' ')}
        role="list"
        aria-label={`${theme.title} drop zone`}
      >
        {tasks.length === 0 ? (
          <EmptyState status={status} planApproved={planApproved} />
        ) : (
          <SortableContext id={`sortable-${status}`} items={ids} strategy={verticalListSortingStrategy}>
            <ul className="flex flex-col gap-2">
              {tasks.map((task) => {
                const meta = agentMap[task.id]
                const aiRunStatus = task.aiRunStatus ?? meta?.status ?? null
                const isAgentRunning =
                  aiRunStatus === 'running' || aiRunStatus === 'paused'
                return (
                  <li key={task.id} className="list-none">
                    <TaskCard
                      task={{ ...task, aiRunStatus }}
                      sortableDisabled={taskCardSortableDisabled}
                      isAgentRunning={isAgentRunning}
                      isReviewSelected={status === 'review' && selectedReviewTaskId === task.id}
                      members={members}
                      currentUserRole={currentUserRole}
                      onAssignUser={
                        onAssignUser ? (userId) => onAssignUser(task.id, userId) : undefined
                      }
                      onView={
                        status === 'review' && onOpenReview ? () => onOpenReview(task.id) : undefined
                      }
                      onReject={onRejectTask ? () => onRejectTask(task.id) : undefined}
                      onSaveAsTemplate={
                        onSaveAsTemplate ? () => onSaveAsTemplate(task) : undefined
                      }
                      onStart={
                        status === 'todo' && onStartTask ? () => onStartTask(task.id) : undefined
                      }
                      startBusy={startingTaskId === task.id}
                      onCancel={
                        status === 'in_progress' && onCancelTask
                          ? () => onCancelTask(task.id)
                          : undefined
                      }
                      cancelBusy={cancellingTaskId === task.id}
                    />
                  </li>
                )
              })}
            </ul>
          </SortableContext>
        )}

        {isLocked ? <WIPLockBlock /> : null}
      </div>

      {/* Footer: add card */}
      {onAddTask ? (
        <footer className="rounded-b-2xl border-t border-slate-200/60 bg-white/60 px-2 py-2">
          <button
            type="button"
            onClick={onAddTask}
            className="group/btn inline-flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-dashed border-slate-300 bg-transparent px-2 py-2 font-mono text-[11.5px] font-medium text-slate-500 transition-all duration-150 hover:border-brand-400 hover:bg-brand-50/50 hover:text-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
            aria-label={`Add task to ${theme.title}`}
          >
            <IconPlus />
            Add a card
          </button>
        </footer>
      ) : null}
    </section>
  )
}
