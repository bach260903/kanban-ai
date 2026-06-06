import Dagre from '@dagrejs/dagre'
import {
  Background,
  BackgroundVariant,
  Controls,
  type Edge,
  Handle,
  MarkerType,
  MiniMap,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { isAxiosError } from 'axios'
import { Plus, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { Spinner } from '../atoms/spinner'
import { showErrorToast, showSuccessToast } from '../../lib/toast'
import {
  addDep,
  getGraph,
  removeDep,
  type DependencyGraphResponse,
} from '../../services/dependency-api'

// ─── Status styling ────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  todo:        { bg: '#f8fafc', border: '#94a3b8', text: '#334155', badge: '#e2e8f0' },
  in_progress: { bg: '#eff6ff', border: '#3b82f6', text: '#1e40af', badge: '#dbeafe' },
  review:      { bg: '#fffbeb', border: '#f59e0b', text: '#92400e', badge: '#fef3c7' },
  done:        { bg: '#f0fdf4', border: '#22c55e', text: '#14532d', badge: '#dcfce7' },
}

const STATUS_LABEL: Record<string, string> = {
  todo: 'Chờ',
  in_progress: 'Đang làm',
  review: 'Review',
  done: 'Xong',
}

// ─── Custom node ────────────────────────────────────────────────────────────

type TaskNodeData = {
  label: string
  status: string
  isBlocked?: boolean
}

function TaskNode({ data }: NodeProps<Node<TaskNodeData>>) {
  const color = STATUS_COLOR[data.status] ?? STATUS_COLOR.todo
  const label = STATUS_LABEL[data.status] ?? data.status
  return (
    <div
      style={{
        background: color.bg,
        borderColor: color.border,
        color: color.text,
        borderWidth: 2,
        borderStyle: 'solid',
        borderRadius: 10,
        padding: '8px 14px',
        minWidth: 150,
        maxWidth: 200,
        boxShadow: '0 2px 8px rgba(0,0,0,.08)',
        fontSize: 12,
        fontFamily: 'inherit',
        position: 'relative',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: color.border }} />
      <div style={{ fontWeight: 600, lineHeight: 1.3, marginBottom: 4, wordBreak: 'break-word' }}>
        {data.label}
      </div>
      <span
        style={{
          background: color.badge,
          borderRadius: 4,
          padding: '1px 6px',
          fontSize: 10,
          fontWeight: 500,
          letterSpacing: '0.02em',
        }}
      >
        {label}
      </span>
      {data.isBlocked && (
        <span
          title="Bị chặn bởi dependency"
          style={{
            position: 'absolute',
            top: 4,
            right: 6,
            fontSize: 11,
          }}
        >
          🔒
        </span>
      )}
      <Handle type="source" position={Position.Right} style={{ background: color.border }} />
    </div>
  )
}

const NODE_TYPES = { task: TaskNode }

// ─── Dagre layout ────────────────────────────────────────────────────────────

const NODE_W = 180
const NODE_H = 64

function applyDagreLayout(
  nodes: Node[],
  edges: Edge[],
): { nodes: Node[]; edges: Edge[] } {
  const g = new Dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', ranksep: 90, nodesep: 50, marginx: 30, marginy: 30 })

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }))
  edges.forEach((e) => g.setEdge(e.source, e.target))

  Dagre.layout(g)

  return {
    nodes: nodes.map((n) => {
      const pos = g.node(n.id)
      return { ...n, position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 } }
    }),
    edges,
  }
}

// ─── Conversion helpers ──────────────────────────────────────────────────────

function buildFlowElements(graph: DependencyGraphResponse): {
  nodes: Node[]
  edges: Edge[]
} {
  const rawNodes: Node[] = graph.nodes.map((n) => ({
    id: n.id,
    type: 'task',
    position: { x: 0, y: 0 },
    data: { label: n.title, status: n.status },
  }))

  const rawEdges: Edge[] = graph.edges.map((e) => ({
    id: `${e.from}-${e.to}`,
    source: e.to,   // "to" = prerequisite (source of arrow)
    target: e.from, // "from" = task that depends (target of arrow)
    markerEnd: { type: MarkerType.ArrowClosed, color: '#64748b' },
    style: { stroke: '#64748b', strokeWidth: 1.5 },
    animated: false,
  }))

  return applyDagreLayout(rawNodes, rawEdges)
}

function truncate(text: string, max = 30): string {
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`
}

function graphErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (err.response?.status === 409) return 'Phát hiện vòng lặp dependency.'
    return err.message
  }
  if (err instanceof Error) return err.message
  return 'Thao tác dependency thất bại.'
}

// ─── Inner component (needs ReactFlow context) ───────────────────────────────

type InnerProps = {
  projectId: string
  graph: DependencyGraphResponse
  onGraphChange: (g: DependencyGraphResponse) => void
}

function DependencyGraphInner({ projectId, graph, onGraphChange }: InnerProps) {
  const { fitView } = useReactFlow()
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [taskId, setTaskId] = useState('')
  const [dependsOnId, setDependsOnId] = useState('')
  const [busy, setBusy] = useState(false)

  // Rebuild flow whenever graph data changes
  useEffect(() => {
    const { nodes: ln, edges: le } = buildFlowElements(graph)
    setNodes(ln)
    setEdges(le)
    setTimeout(() => fitView({ padding: 0.15, duration: 400 }), 50)
  }, [graph, setNodes, setEdges, fitView])

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
      showSuccessToast('Đã thêm dependency.')
      setDependsOnId('')
      const updated = await getGraph(projectId)
      onGraphChange(updated)
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
      showSuccessToast('Đã xóa dependency.')
      const updated = await getGraph(projectId)
      onGraphChange(updated)
    } catch (err) {
      showErrorToast(graphErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const taskNodes = graph.nodes
  const edges_list = graph.edges

  // Node lookup map
  const nodeById = useMemo(
    () => new Map(taskNodes.map((n) => [n.id, n])),
    [taskNodes],
  )

  return (
    <div style={{ display: 'flex', gap: 16, height: '100%', minHeight: 520 }}>
      {/* ── Graph canvas ─────────────────────────────────── */}
      <div style={{ flex: 1, borderRadius: 12, overflow: 'hidden', border: '1px solid #e2e8f0', background: '#fafafa' }}>
        {taskNodes.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', fontSize: 14 }}>
            Chưa có task nào trong dự án.
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={NODE_TYPES}
            fitView
            proOptions={{ hideAttribution: true }}
            minZoom={0.3}
            maxZoom={2}
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#e2e8f0" />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                const status = (n.data as TaskNodeData).status
                return STATUS_COLOR[status]?.border ?? '#94a3b8'
              }}
              maskColor="rgba(248,250,252,0.7)"
            />
          </ReactFlow>
        )}
      </div>

      {/* ── Right panel ──────────────────────────────────── */}
      <aside style={{ width: 300, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>

        {/* Add dependency manually */}
        <div style={{ borderRadius: 12, border: '1px solid #e2e8f0', background: '#fff', padding: 16 }}>
          <h3 style={{ margin: '0 0 4px', fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#475569', fontFamily: 'monospace' }}>
            Thêm thủ công
          </h3>
          <p style={{ margin: '0 0 10px', fontSize: 12, color: '#64748b' }}>Task bên dưới phụ thuộc vào prerequisite.</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: '#374151' }}>
              Task (phụ thuộc)
              <select
                value={taskId}
                onChange={(e) => setTaskId(e.target.value)}
                disabled={busy}
                style={{ display: 'block', width: '100%', marginTop: 4, padding: '6px 8px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 12 }}
              >
                <option value="">Chọn task…</option>
                {taskNodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    {truncate(n.title, 38)} ({STATUS_LABEL[n.status] ?? n.status})
                  </option>
                ))}
              </select>
            </label>
            <label style={{ fontSize: 12, fontWeight: 500, color: '#374151' }}>
              Phụ thuộc vào
              <select
                value={dependsOnId}
                onChange={(e) => setDependsOnId(e.target.value)}
                disabled={busy}
                style={{ display: 'block', width: '100%', marginTop: 4, padding: '6px 8px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 12 }}
              >
                <option value="">Chọn prerequisite…</option>
                {taskNodes.filter((n) => n.id !== taskId).map((n) => (
                  <option key={n.id} value={n.id}>
                    {truncate(n.title, 38)} ({STATUS_LABEL[n.status] ?? n.status})
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={busy || !taskId || !dependsOnId}
              onClick={() => void handleAdd()}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                padding: '7px 14px', borderRadius: 8, border: 'none',
                background: (!taskId || !dependsOnId || busy) ? '#e2e8f0' : '#0f172a',
                color: (!taskId || !dependsOnId || busy) ? '#94a3b8' : '#fff',
                fontSize: 12, fontWeight: 600, cursor: (!taskId || !dependsOnId || busy) ? 'not-allowed' : 'pointer',
              }}
            >
              <Plus size={13} />
              {busy ? 'Đang lưu…' : 'Thêm dependency'}
            </button>
          </div>
        </div>

        {/* Current dependencies list */}
        <div style={{ borderRadius: 12, border: '1px solid #e2e8f0', background: '#fff', padding: 16, flex: 1, minHeight: 0 }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#475569', fontFamily: 'monospace' }}>
            Danh sách dependency ({edges_list.length})
          </h3>
          {edges_list.length === 0 ? (
            <p style={{ fontSize: 12, color: '#94a3b8', margin: 0 }}>Chưa có dependency nào.</p>
          ) : (
            <ul style={{ margin: 0, padding: 0, listStyle: 'none', maxHeight: 240, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
              {edges_list.map((edge) => {
                const from = nodeById.get(edge.from)
                const to = nodeById.get(edge.to)
                const fromColor = STATUS_COLOR[from?.status ?? ''] ?? STATUS_COLOR.todo
                const toColor = STATUS_COLOR[to?.status ?? ''] ?? STATUS_COLOR.todo
                return (
                  <li key={`${edge.from}-${edge.to}`} style={{ background: '#f8fafc', borderRadius: 8, padding: '8px 10px', fontSize: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6 }}>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <span
                          title={from?.title}
                          style={{ fontWeight: 600, color: fromColor.text, display: 'inline-block', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        >
                          {truncate(from?.title ?? edge.from, 26)}
                        </span>
                        <span style={{ color: '#94a3b8', fontSize: 11, display: 'block', margin: '2px 0' }}>
                          ← cần hoàn thành trước:
                        </span>
                        <span
                          title={to?.title}
                          style={{ color: toColor.text, display: 'inline-block', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        >
                          {truncate(to?.title ?? edge.to, 26)}
                        </span>
                      </div>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void handleRemove(edge.from, edge.to)}
                        title="Xóa dependency"
                        style={{ flexShrink: 0, background: 'none', border: 'none', cursor: busy ? 'not-allowed' : 'pointer', color: '#f43f5e', padding: 2 }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </aside>
    </div>
  )
}

// ─── Public component (provides ReactFlow context) ───────────────────────────

import { ReactFlowProvider } from '@xyflow/react'

export type DependencyGraphProps = {
  projectId: string
  onChanged?: () => void
}

export function DependencyGraph({ projectId, onChanged }: DependencyGraphProps) {
  const [graph, setGraph] = useState<DependencyGraphResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadGraph = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getGraph(projectId)
      setGraph(data)
    } catch (err) {
      setError(graphErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    void loadGraph()
  }, [loadGraph])

  const handleGraphChange = useCallback(
    (updated: DependencyGraphResponse) => {
      setGraph(updated)
      onChanged?.()
    },
    [onChanged],
  )

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, gap: 8, color: '#64748b' }}>
        <Spinner aria-label="Đang tải…" />
        <span style={{ fontSize: 13 }}>Đang tải dependency graph…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ borderRadius: 10, border: '1px solid #fca5a5', background: '#fff1f2', padding: '12px 16px', fontSize: 13, color: '#be123c' }}>
        {error}
        <button
          type="button"
          onClick={() => void loadGraph()}
          style={{ marginLeft: 12, fontSize: 12, color: '#be123c', textDecoration: 'underline', background: 'none', border: 'none', cursor: 'pointer' }}
        >
          Thử lại
        </button>
      </div>
    )
  }

  return (
    <ReactFlowProvider>
      <DependencyGraphInner
        projectId={projectId}
        graph={graph ?? { nodes: [], edges: [] }}
        onGraphChange={handleGraphChange}
      />
    </ReactFlowProvider>
  )
}
