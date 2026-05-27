import { DndContext, DragOverlay, type DragStartEvent } from '@dnd-kit/core'
import { isAxiosError } from 'axios'
import { useEffect, useMemo, useState } from 'react'

import { Spinner } from '../atoms/spinner'
import { CreateTaskModal } from '../molecules/create-task-modal'
import { SaveAsTemplateModal } from '../molecules/save-as-template-modal'
import { KanbanColumn } from './kanban-column'
import { TaskCard, type TaskCardData } from './task-card'
import { WIPWarning } from './wip-warning'
import { useAuth } from '../../contexts/auth-context'
import { useKanban } from '../../hooks/use-kanban'
import { showErrorToast, showSuccessToast } from '../../lib/toast'
import { getMembers } from '../../services/member-api'
import { getGraph, type DependencyGraphResponse } from '../../services/dependency-api'
import { assignTask, cancelTask, getTasks, groupedResponseToTaskColumns } from '../../services/task-api'
import { emptyTaskColumns, useTaskStore, type TaskColumnItem, type TaskColumns } from '../../store/task-store'
import type { ProjectMember, ProjectRole, TaskStatus } from '../../types'
import { buildBlockedByTitlesMap, buildDependsOnCountMap } from '../../utils/dependency-map'
import { isMultiUserWipMode, isUserWipFull } from '../../utils/wip-limit'

const BOARD_STATUSES = [
  'todo',
  'in_progress',
  'review',
  'done',
  'rejected',
  'conflict',
] as const satisfies readonly TaskStatus[]

export type KanbanBoardProps = {
  projectId: string
  planApproved?: boolean
  selectedReviewTaskId?: string | null
  onSelectReviewTask?: (taskId: string) => void
  onRejectTask?: (taskId: string) => void
  onAddTask?: (status: TaskStatus) => void
}

function loadErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    return err.message
  }
  if (err instanceof Error) return err.message
  return 'Unable to load tasks.'
}

function findTaskById(
  columns: Record<TaskStatus, TaskColumnItem[]>,
  taskId: string,
): TaskColumnItem | null {
  for (const status of BOARD_STATUSES) {
    const found = columns[status].find((t) => t.id === taskId)
    if (found) return found
  }
  return null
}

function enrichColumnsWithDeps(
  columns: TaskColumns,
  graph: DependencyGraphResponse | null,
): Record<TaskStatus, TaskCardData[]> {
  const blockedByMap = graph ? buildBlockedByTitlesMap(graph) : new Map<string, string[]>()
  const dependsOnMap = graph ? buildDependsOnCountMap(graph) : new Map<string, number>()
  const enrich = (items: TaskColumnItem[]): TaskCardData[] =>
    items.map((t) => ({
      ...t,
      blockedByTitles: blockedByMap.get(t.id) ?? [],
      dependsOnCount: dependsOnMap.get(t.id) ?? 0,
    }))
  return {
    todo: enrich(columns.todo),
    in_progress: enrich(columns.in_progress),
    review: enrich(columns.review),
    done: enrich(columns.done),
    rejected: enrich(columns.rejected),
    conflict: enrich(columns.conflict),
  }
}

export function KanbanBoard({
  projectId,
  planApproved = false,
  selectedReviewTaskId = null,
  onSelectReviewTask,
  onRejectTask,
  onAddTask,
}: KanbanBoardProps) {
  const { user } = useAuth()
  const columns = useTaskStore((s) => s.columns)
  const setColumns = useTaskStore((s) => s.setColumns)
  const clearTaskAgentRuns = useTaskStore((s) => s.clearTaskAgentRuns)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [startingTaskId, setStartingTaskId] = useState<string | null>(null)
  const [cancellingTaskId, setCancellingTaskId] = useState<string | null>(null)
  const [activeDragId, setActiveDragId] = useState<string | null>(null)
  const [depGraph, setDepGraph] = useState<DependencyGraphResponse | null>(null)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [saveTemplateTask, setSaveTemplateTask] = useState<{
    title: string
    description: string | null
  } | null>(null)

  const [wipWarning, setWipWarning] = useState<{ open: boolean; currentTaskTitle?: string }>({
    open: false,
  })

  const { sensors, collisionDetection, onDragEnd, startTask } = useKanban(projectId, {
    currentUserId: user?.id,
    isMultiUser: isMultiUserWipMode(members.length),
  })

  const multiUserWip = isMultiUserWipMode(members.length)

  const currentUserRole = useMemo<ProjectRole | undefined>(() => {
    if (!user) return undefined
    return members.find((m) => m.user_id === user.id)?.role
  }, [members, user])

  const canManageTemplates = currentUserRole === 'owner' || currentUserRole === 'leader'
  const canCreateTask =
    currentUserRole === 'owner' ||
    currentUserRole === 'leader' ||
    currentUserRole === 'developer'

  const handleAddTaskClick = () => {
    if (onAddTask) {
      onAddTask('todo')
      return
    }
    setCreateModalOpen(true)
  }

  const handleDragStart = (event: DragStartEvent) => {
    const taskId = String(event.active.id)
    const task = findTaskById(columns, taskId)
    if (task?.is_blocked) {
      showErrorToast('Task đang bị blocked.')
      return
    }
    setActiveDragId(taskId)
  }

  const handleDragEnd = (event: Parameters<typeof onDragEnd>[0]) => {
    setActiveDragId(null)
    const activeId = String(event.active.id)
    const task = findTaskById(columns, activeId)
    if (task?.is_blocked) {
      showErrorToast('Task đang bị blocked.')
      return
    }
    const overData = event.over?.data.current as { type?: string; status?: TaskStatus } | undefined

    if (overData?.type === 'column' && overData.status === 'in_progress') {
      const fromTodo = columns.todo.some((t) => t.id === activeId)
      if (fromTodo && isUserWipFull(columns, user?.id, multiUserWip)) {
        const current = multiUserWip
          ? columns.in_progress.find((t) => t.assigned_to === user?.id)
          : columns.in_progress[0]
        setWipWarning({ open: true, currentTaskTitle: current?.title })
        return
      }
    }

    onDragEnd(event)
  }

  const handleStartTask = (taskId: string) => {
    const task = findTaskById(columns, taskId)
    if (task?.is_blocked) {
      showErrorToast('Task đang bị blocked.')
      return
    }
    if (isUserWipFull(columns, user?.id, multiUserWip)) {
      const current = multiUserWip
        ? columns.in_progress.find((t) => t.assigned_to === user?.id)
        : columns.in_progress[0]
      setWipWarning({ open: true, currentTaskTitle: current?.title })
      return
    }
    setStartingTaskId(taskId)
    startTask(taskId)
    window.setTimeout(() => setStartingTaskId(null), 800)
  }

  const handleCancelTask = async (taskId: string) => {
    setCancellingTaskId(taskId)
    try {
      await cancelTask(projectId, taskId)
      await refreshBoardData()
      showSuccessToast('Task cancelled and moved back to To do.')
    } catch (err) {
      showErrorToast(loadErrorMessage(err))
    } finally {
      setCancellingTaskId(null)
    }
  }

  const handleAssignUser = async (taskId: string, userId: string | null) => {
    try {
      await assignTask(projectId, taskId, userId)
      await refreshBoardData()
      showSuccessToast(userId ? 'Task assigned.' : 'Task unassigned.')
    } catch (err) {
      showErrorToast(loadErrorMessage(err))
    }
  }

  const enrichedColumns = useMemo(
    () => enrichColumnsWithDeps(columns, depGraph),
    [columns, depGraph],
  )

  const tasksSignature = useMemo(
    () =>
      BOARD_STATUSES.map((status) =>
        columns[status]
          .map((t) => `${t.id}:${t.status}:${t.is_blocked ? 1 : 0}`)
          .sort()
          .join(','),
      ).join('|'),
    [columns],
  )

  const refreshBoardData = async () => {
    const [data, graph] = await Promise.all([
      getTasks(projectId),
      getGraph(projectId).catch(() => null),
    ])
    clearTaskAgentRuns()
    setColumns(groupedResponseToTaskColumns(data))
    setDepGraph(graph)
  }

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const [data, graph] = await Promise.all([
          getTasks(projectId),
          getGraph(projectId).catch(() => null),
        ])
        if (!cancelled) {
          clearTaskAgentRuns()
          setColumns(groupedResponseToTaskColumns(data))
          setDepGraph(graph)
        }
        try {
          const memberRows = await getMembers(projectId)
          if (!cancelled) setMembers(memberRows)
        } catch {
          if (!cancelled) setMembers([])
        }
      } catch (err) {
        if (!cancelled) {
          setError(loadErrorMessage(err))
          clearTaskAgentRuns()
          setColumns(emptyTaskColumns())
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [projectId, setColumns, clearTaskAgentRuns])

  useEffect(() => {
    if (loading) return
    let cancelled = false
    void getGraph(projectId)
      .then((graph) => {
        if (!cancelled) setDepGraph(graph)
      })
      .catch(() => {
        if (!cancelled) setDepGraph(null)
      })
    return () => {
      cancelled = true
    }
  }, [projectId, loading, tasksSignature])

  const activeTask = useMemo<TaskCardData | null>(() => {
    if (!activeDragId) return null
    for (const status of BOARD_STATUSES) {
      const found = enrichedColumns[status].find((t) => t.id === activeDragId)
      if (found) return found
    }
    return null
  }, [activeDragId, enrichedColumns])

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-slate-500">
        <Spinner aria-label="Loading Kanban tasks" />
        <span className="font-mono text-sm">Loading tasks…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <p
          role="alert"
          className="max-w-md rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-center text-sm font-medium text-red-700"
        >
          {error}
        </p>
      </div>
    )
  }

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-gradient-to-br from-brand-50/50 via-white to-slate-50">
      {/* Toolbar */}
      <div className="flex flex-shrink-0 items-center justify-between border-b border-slate-200/70 bg-white/80 px-4 py-2.5 backdrop-blur">
        <div className="flex items-center gap-2">
          <span className="font-display text-[14px] font-semibold tracking-tight text-slate-900">
            Kanban board
          </span>
          <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">
            {BOARD_STATUSES.length} columns · {multiUserWip ? 'WIP = 1 per dev' : 'WIP = 1'}
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px]">
          <LegendDot tone="bg-brand-500" label="In progress" />
          <LegendDot tone="bg-violet-500" label="Review" />
          <LegendDot tone="bg-emerald-500" label="Done" />
        </div>
      </div>

      {/* Board scroll area */}
      <DndContext
        sensors={sensors}
        collisionDetection={collisionDetection}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={() => setActiveDragId(null)}
      >
        <div
          className="kanban-scroll flex flex-1 items-stretch gap-3 overflow-x-auto overflow-y-hidden p-3 sm:p-4 [scroll-snap-type:x_mandatory] [scroll-padding-inline:1rem]"
          role="region"
          aria-label="Kanban board"
        >
          {BOARD_STATUSES.map((status) => (
            <KanbanColumn
              key={status}
              column={{ status, tasks: enrichedColumns[status] }}
              taskCardSortableDisabled={status !== 'todo'}
              isWipColumn={status === 'in_progress'}
              wipLimit={1}
              multiUserWip={multiUserWip}
              currentUserId={user?.id}
              planApproved={planApproved}
              onAddTask={
                planApproved && canCreateTask && status === 'todo' ? handleAddTaskClick : undefined
              }
              onStartTask={status === 'todo' ? handleStartTask : undefined}
              startingTaskId={startingTaskId}
              selectedReviewTaskId={selectedReviewTaskId}
              onOpenReview={onSelectReviewTask}
              onCancelTask={handleCancelTask}
              cancellingTaskId={cancellingTaskId}
              members={members}
              currentUserRole={currentUserRole}
              onAssignUser={handleAssignUser}
              onRejectTask={onRejectTask}
              onSaveAsTemplate={
                canManageTemplates
                  ? (task) =>
                      setSaveTemplateTask({
                        title: task.title,
                        description: task.description,
                      })
                  : undefined
              }
            />
          ))}
        </div>

        <DragOverlay dropAnimation={null}>
          {activeTask ? (
            <div className="w-[280px] rotate-2 opacity-90">
              <TaskCard task={activeTask} sortableDisabled />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      <WIPWarning
        open={wipWarning.open}
        variant="toast"
        currentTaskTitle={wipWarning.currentTaskTitle}
        onDismiss={() => setWipWarning({ open: false })}
      />

      <CreateTaskModal
        open={createModalOpen}
        projectId={projectId}
        onClose={() => setCreateModalOpen(false)}
        onCreated={() => void refreshBoardData()}
      />

      {saveTemplateTask ? (
        <SaveAsTemplateModal
          open
          projectId={projectId}
          taskTitle={saveTemplateTask.title}
          taskDescription={saveTemplateTask.description}
          onClose={() => setSaveTemplateTask(null)}
        />
      ) : null}
    </div>
  )
}

function LegendDot({ tone, label }: { tone: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 font-mono uppercase tracking-wider text-slate-500">
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${tone}`} />
      {label}
    </span>
  )
}
