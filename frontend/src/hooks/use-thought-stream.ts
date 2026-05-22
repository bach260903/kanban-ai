import { useCallback, useEffect, useRef, useState } from 'react'

import { TaskThoughtStreamClient } from '../services/websocket-client'

type StreamEntry = {
  msg: Record<string, unknown>
  order: number
}

function compareEntries(a: StreamEntry, b: StreamEntry): number {
  const sa = a.msg.sequence_number
  const sb = b.msg.sequence_number
  const ha = typeof sa === 'number' && !Number.isNaN(sa)
  const hb = typeof sb === 'number' && !Number.isNaN(sb)
  if (ha && hb) return sa - sb
  if (ha) return -1
  if (hb) return 1
  return a.order - b.order
}

function isRenderableStreamMessage(msg: Record<string, unknown>): boolean {
  return (
    msg.type != null ||
    msg.event_type != null ||
    typeof msg.sequence_number === 'number' ||
    typeof msg.id === 'string'
  )
}

function parseStreamContent(msg: Record<string, unknown>): Record<string, unknown> | null {
  const raw = msg.content
  if (raw == null) return null
  if (typeof raw === 'object' && !Array.isArray(raw)) {
    return raw as Record<string, unknown>
  }
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw) as unknown
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
    } catch {
      return null
    }
  }
  return null
}

/** Kanban columns should reload when coder moves task to review (events arrive before poll). */
export function shouldSyncKanbanFromStream(msg: Record<string, unknown>): boolean {
  const frameType = msg.type
  if (frameType === 'STREAM_END') return true

  const eventType = typeof msg.event_type === 'string' ? msg.event_type : null
  if (eventType === 'STATUS_CHANGE') {
    const body = parseStreamContent(msg)
    return body?.to === 'REVIEWING'
  }
  if (eventType === 'ACTION') {
    const body = parseStreamContent(msg)
    const inner = body?.type
    return inner === 'REVIEW_SCORE' || inner === 'REVIEW_COMMENT'
  }
  return false
}

export type UseThoughtStreamResult = {
  events: Record<string, unknown>[]
  isConnected: boolean
  streamEnded: boolean
  /** Send control frames (e.g. ``PAUSE`` / ``RESUME``) on the same socket (US11 / T089–T090 → {@link TaskThoughtStreamClient.send}). */
  send: (message: Record<string, unknown> | string) => void
}

/**
 * Subscribes to {@link TaskThoughtStreamClient}, keeps `events` ordered by `sequence_number`
 * (non-sequenced frames ordered by arrival). US10 / T081.
 */
export function useThoughtStream(
  taskId: string | null,
  onStreamEnded?: () => void,
): UseThoughtStreamResult {
  const [events, setEvents] = useState<Record<string, unknown>[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [streamEnded, setStreamEnded] = useState(false)

  const orderRef = useRef(0)
  const seenSeqRef = useRef(new Set<number>())
  const seenIdRef = useRef(new Set<string>())
  const entriesRef = useRef<StreamEntry[]>([])
  const clientRef = useRef<TaskThoughtStreamClient | null>(null)

  const send = useCallback((message: Record<string, unknown> | string) => {
    clientRef.current?.send(message)
  }, [])

  useEffect(() => {
    seenSeqRef.current.clear()
    seenIdRef.current.clear()
    entriesRef.current = []
    orderRef.current = 0
    setEvents([])
    setStreamEnded(false)
    setIsConnected(false)
    clientRef.current = null

    if (taskId == null || taskId === '') {
      return undefined
    }

    const client = new TaskThoughtStreamClient(taskId)
    clientRef.current = client

    const offConn = client.onConnectionChange(setIsConnected)

    const offEv = client.onEvent((msg) => {
      if (msg.type === 'STREAM_END') {
        setStreamEnded(true)
      }
      if (msg.type === 'ERROR' && msg.code === 'TASK_NOT_ACTIVE') {
        setStreamEnded(true)
      }
      if (shouldSyncKanbanFromStream(msg)) {
        onStreamEnded?.()
      }

      if (!isRenderableStreamMessage(msg)) {
        return
      }

      const mid = msg.id
      if (typeof mid === 'string' && mid.length > 0) {
        if (seenIdRef.current.has(mid)) {
          return
        }
        seenIdRef.current.add(mid)
      } else {
        const sq = msg.sequence_number
        if (typeof sq === 'number' && !Number.isNaN(sq)) {
          if (seenSeqRef.current.has(sq)) {
            return
          }
          seenSeqRef.current.add(sq)
        }
      }

      const order = orderRef.current++
      let next = entriesRef.current
      if (msg.type === 'CONNECTED') {
        next = next.filter((e) => e.msg.type !== 'CONNECTED')
      }
      next = [...next, { msg, order }].sort(compareEntries)
      entriesRef.current = next
      setEvents(next.map((e) => e.msg))
    })

    client.connect()

    return () => {
      offConn()
      offEv()
      client.disconnect()
      clientRef.current = null
    }
  }, [taskId])

  useEffect(() => {
    if (streamEnded) onStreamEnded?.()
  }, [streamEnded, onStreamEnded])

  return { events, isConnected, streamEnded, send }
}
