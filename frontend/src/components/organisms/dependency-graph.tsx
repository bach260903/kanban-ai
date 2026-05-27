import { isAxiosError } from 'axios'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { Spinner } from '../atoms/spinner'
import { showErrorToast, showSuccessToast } from '../../lib/toast'
import {
  addDep,
  getGraph,
  removeDep,
  type DependencyGraphNode,
  type DependencyGraphResponse,
} from '../../services/dependency-api'

const SVG_WIDTH = 900
const SVG_HEIGHT = 500
const NODE_W = 120
const NODE_H = 40

const STATUS_X: Record<string, number> = {
  todo: 100,
  in_progress: 300,
  review: 500,
  done: 700,
  rejected: 100,
  conflict: 100,
}

const STATUS_FILL: Record<string, string> = {
  todo: '#e2e8f0',
  in_progress: '#dbeafe',
  review: '#fef3c7',
  done: '#d1fae5',
  rejected: '#fee2e2',
  conflict: '#fef3c7',
}

const STATUS_STROKE: Record<string, string> = {
  todo: '#94a3b8',
  in_progress: '#3b82f6',
  review: '#d97706',
  done: '#10b981',
  rejected: '#ef4444',
  conflict: '#f59e0b',
}

const COLUMN_LABELS: { x: number; label: string }[] = [
  { x: 100, label: 'To do' },
  { x: 300, label: 'In progress' },
  { x: 500, label: 'Review' },
  { x: 700, label: 'Done' },
]

function truncate(text: string, max = 15): string {
  const t = text.trim()
  if (t.length <= max) return t
  return `${t.slice(0, max - 1)}…`
}

function layoutNodes(
  nodes: DependencyGraphNode[],
): { positions: Map<string, { x: number; y: number }>; height: number } {
  const byColumn = new Map<number, DependencyGraphNode[]>()
  for (const node of nodes) {
    const colX = STATUS_X[node.status] ?? 100
    const list = byColumn.get(colX) ?? []
    list.push(node)
    byColumn.set(colX, list)
  }

  const positions = new Map<string, { x: number; y: number }>()
  let maxY = SVG_HEIGHT
  for (const [colX, colNodes] of byColumn.entries()) {
    colNodes
      .sort((a, b) => a.title.localeCompare(b.title))
      .forEach((node, index) => {
        const y = 48 + index * (NODE_H + 18)
        positions.set(node.id, {
          x: colX - NODE_W / 2,
          y,
        })
        maxY = Math.max(maxY, y + NODE_H + 24)
      })
  }
  return { positions, height: maxY }
}

function graphErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (err.response?.status === 409) return 'Circular dependency detected.'
    return err.message
  }
  if (err instanceof Error) return err.message
  return 'Dependency operation failed.'
}

export type DependencyGraphProps = {
  projectId: string
  onChanged?: () => void
}

export function DependencyGraph({ projectId, onChanged }: DependencyGraphProps) {
  const [graph, setGraph] = useState<DependencyGraphResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [taskId, setTaskId] = useState('')
  const [dependsOnId, setDependsOnId] = useState('')
  const [busy, setBusy] = useState(false)

  const loadGraph = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setLoading(true)
      setError(null)
    }
    try {
      const data = await getGraph(projectId)
      setGraph(data)
      setError(null)
    } catch (err) {
      if (!options?.silent) {
        setError(graphErrorMessage(err))
        setGraph(null)
      }
    } finally {
      if (!options?.silent) setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    void loadGraph()
  }, [loadGraph])

  const { positions, svgHeight } = useMemo(() => {
    const laid = layoutNodes(graph?.nodes ?? [])
    return { positions: laid.positions, svgHeight: laid.height }
  }, [graph?.nodes])

  const nodeById = useMemo(
    () => new Map((graph?.nodes ?? []).map((n) => [n.id, n])),
    [graph?.nodes],
  )

  const edges = graph?.edges ?? []
  const nodes = graph?.nodes ?? []

  const handleAdd = async () => {
    if (!taskId || !dependsOnId) {
      showErrorToast('Chọn task và prerequisite.')
      return
    }
    if (taskId === dependsOnId) {
      showErrorToast('Task không thể phụ thuộc chính nó.')
      return
    }
    setBusy(true)
    try {
      await addDep(projectId, taskId, dependsOnId)
      showSuccessToast('Dependency added.')
      setDependsOnId('')
      await loadGraph({ silent: true })
      onChanged?.()
    } catch (err) {
      showErrorToast(graphErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const handleRemove = async (fromTaskId: string, toTaskId: string) => {
    setBusy(true)
    try {
      await removeDep(projectId, fromTaskId, toTaskId)
      showSuccessToast('Dependency removed.')
      await loadGraph({ silent: true })
      onChanged?.()
    } catch (err) {
      showErrorToast(graphErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center gap-2 text-slate-500">
        <Spinner aria-label="Loading dependency graph" />
        <span className="font-mono text-sm">Loading graph…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
        {error}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <div className="min-w-0 flex-1 overflow-x-auto rounded-xl border border-slate-200 bg-white p-4 shadow-elev-1">
        <svg
          viewBox={`0 0 ${SVG_WIDTH} ${svgHeight}`}
          width={SVG_WIDTH}
          height={svgHeight}
          className="mx-auto max-w-full"
          role="img"
          aria-label="Task dependency graph"
        >
          <defs>
            <marker
              id="dep-arrow"
              markerWidth="8"
              markerHeight="8"
              refX="7"
              refY="4"
              orient="auto"
            >
              <path d="M0,0 L8,4 L0,8 Z" fill="#64748b" />
            </marker>
          </defs>

          {COLUMN_LABELS.map(({ x, label }) => (
            <text
              key={label}
              x={x}
              y={24}
              textAnchor="middle"
              className="fill-slate-500 font-mono text-[11px] font-semibold uppercase tracking-wider"
            >
              {label}
            </text>
          ))}

          {edges.map((edge) => {
            const fromPos = positions.get(edge.from)
            const toPos = positions.get(edge.to)
            if (!fromPos || !toPos) return null
            const x1 = toPos.x + NODE_W
            const y1 = toPos.y + NODE_H / 2
            const x2 = fromPos.x
            const y2 = fromPos.y + NODE_H / 2
            return (
              <line
                key={`${edge.from}-${edge.to}`}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="#64748b"
                strokeWidth={1.5}
                markerEnd="url(#dep-arrow)"
              />
            )
          })}

          {nodes.map((node) => {
            const pos = positions.get(node.id)
            if (!pos) return null
            const fill = STATUS_FILL[node.status] ?? STATUS_FILL.todo
            const stroke = STATUS_STROKE[node.status] ?? STATUS_STROKE.todo
            return (
              <g key={node.id}>
                <rect
                  x={pos.x}
                  y={pos.y}
                  width={NODE_W}
                  height={NODE_H}
                  rx={6}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={1.5}
                />
                <text
                  x={pos.x + NODE_W / 2}
                  y={pos.y + NODE_H / 2 + 4}
                  textAnchor="middle"
                  className="fill-slate-800 font-sans text-[11px] font-medium"
                >
                  {truncate(node.title)}
                </text>
              </g>
            )
          })}
        </svg>

        {nodes.length === 0 ? (
          <p className="mt-2 text-center text-sm text-slate-500">No tasks in this project yet.</p>
        ) : null}
      </div>

      <aside className="w-full flex-shrink-0 space-y-4 lg:w-80">
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-elev-1">
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-600">
            Add dependency
          </h3>
          <p className="mt-1 text-[12px] text-slate-500">
            Task below depends on the selected prerequisite.
          </p>
          <div className="mt-3 space-y-2">
            <label className="block text-[12px] font-medium text-slate-700">
              Task (dependent)
              <select
                className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                value={taskId}
                onChange={(e) => setTaskId(e.target.value)}
                disabled={busy}
              >
                <option value="">Select task…</option>
                {nodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    {truncate(n.title, 40)} ({n.status})
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-[12px] font-medium text-slate-700">
              Depends on
              <select
                className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                value={dependsOnId}
                onChange={(e) => setDependsOnId(e.target.value)}
                disabled={busy}
              >
                <option value="">Select prerequisite…</option>
                {nodes
                  .filter((n) => n.id !== taskId)
                  .map((n) => (
                    <option key={n.id} value={n.id}>
                      {truncate(n.title, 40)} ({n.status})
                    </option>
                  ))}
              </select>
            </label>
            <button
              type="button"
              disabled={busy || !taskId || !dependsOnId}
              onClick={() => void handleAdd()}
              className="inline-flex w-full cursor-pointer items-center justify-center rounded-lg bg-cta px-3 py-2 font-mono text-xs font-semibold text-white transition hover:bg-cta-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? 'Saving…' : 'Add dependency'}
            </button>
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-elev-1">
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-600">
            Current dependencies
          </h3>
          {edges.length === 0 ? (
            <p className="mt-2 text-[12px] text-slate-500">No dependencies defined.</p>
          ) : (
            <ul className="mt-2 max-h-64 space-y-2 overflow-y-auto">
              {edges.map((edge) => {
                const from = nodeById.get(edge.from)
                const to = nodeById.get(edge.to)
                return (
                  <li
                    key={`${edge.from}-${edge.to}`}
                    className="flex items-start justify-between gap-2 rounded-lg bg-slate-50 px-2 py-1.5 text-[12px]"
                  >
                    <span className="min-w-0 text-slate-700">
                      <strong>{truncate(from?.title ?? edge.from, 20)}</strong>
                      <span className="text-slate-400"> → </span>
                      {truncate(to?.title ?? edge.to, 20)}
                    </span>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleRemove(edge.from, edge.to)}
                      className="flex-shrink-0 cursor-pointer font-mono text-[10px] font-semibold uppercase text-red-600 hover:text-red-800 disabled:opacity-50"
                    >
                      Remove
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </aside>
    </div>
  )
}
