import { useEffect, useRef, useState } from 'react'

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

export type UseThoughtStreamResult = {
  events: Record<string, unknown>[]
  isConnected: boolean
  streamEnded: boolean
}

/**
 * Subscribes to {@link TaskThoughtStreamClient}, keeps `events` ordered by `sequence_number`
 * (non-sequenced frames ordered by arrival). US10 / T081.
 */
export function useThoughtStream(taskId: string | null): UseThoughtStreamResult {
  const [events, setEvents] = useState<Record<string, unknown>[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [streamEnded, setStreamEnded] = useState(false)

  const orderRef = useRef(0)
  const seenSeqRef = useRef(new Set<number>())
  const seenIdRef = useRef(new Set<string>())
  const entriesRef = useRef<StreamEntry[]>([])

  useEffect(() => {
    seenSeqRef.current.clear()
    seenIdRef.current.clear()
    entriesRef.current = []
    orderRef.current = 0
    setEvents([])
    setStreamEnded(false)
    setIsConnected(false)

    if (taskId == null || taskId === '') {
      return undefined
    }

    const client = new TaskThoughtStreamClient(taskId)

    const offConn = client.onConnectionChange(setIsConnected)

    const offEv = client.onEvent((msg) => {
      if (msg.type === 'STREAM_END') {
        setStreamEnded(true)
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
    }
  }, [taskId])

  return { events, isConnected, streamEnded }
}
