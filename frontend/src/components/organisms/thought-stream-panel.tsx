import { useLayoutEffect, useMemo, useRef } from 'react'

import { useThoughtStream } from '../../hooks/use-thought-stream'
import { PauseResumeControls } from '../molecules/pause-resume-controls'

import styles from './thought-stream-panel.module.css'

export type ThoughtStreamPanelProps = {
  taskId: string | null
  /** Fills parent flex column (slide-in drawer); compact chrome. */
  embedded?: boolean
}

function eventKind(msg: Record<string, unknown>): string {
  const t = msg.type
  if (t === 'CONNECTED') return 'CONNECTED'
  if (t === 'STREAM_END') return 'STREAM_END'
  if (t === 'ERROR') return 'ERROR'
  if (t === 'CLIENT_ERROR') return 'CLIENT_ERROR'
  const et = msg.event_type
  if (typeof et === 'string') return et
  return 'MESSAGE'
}

function labelClass(kind: string): string {
  switch (kind) {
    case 'THOUGHT':
      return styles.labelThought
    case 'TOOL_CALL':
      return styles.labelToolCall
    case 'TOOL_RESULT':
      return styles.labelToolResult
    case 'ACTION':
      return styles.labelAction
    case 'ERROR':
      return styles.labelError
    case 'STATUS_CHANGE':
      return styles.labelStatus
    case 'CONNECTED':
    case 'CLIENT_ERROR':
      return styles.labelControl
    case 'STREAM_END':
      return styles.labelStreamEnd
    default:
      return styles.labelDefault
  }
}

function formatTimestamp(ts: unknown): string {
  if (ts == null || ts === '') return '—'
  if (typeof ts === 'string') {
    const d = new Date(ts)
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        day: '2-digit',
        month: 'short',
      })
    }
    return ts
  }
  return String(ts)
}

function formatPayloadContent(msg: Record<string, unknown>): string {
  const raw = msg.content
  if (raw == null) return ''
  if (typeof raw === 'object') {
    try {
      return JSON.stringify(raw, null, 2)
    } catch {
      return String(raw)
    }
  }
  if (typeof raw === 'string') {
    const s = raw.trim()
    if ((s.startsWith('{') && s.endsWith('}')) || (s.startsWith('[') && s.endsWith(']'))) {
      try {
        return JSON.stringify(JSON.parse(s), null, 2)
      } catch {
        return raw.length > 4000 ? `${raw.slice(0, 4000)}…` : raw
      }
    }
    return raw.length > 4000 ? `${raw.slice(0, 4000)}…` : raw
  }
  return String(raw)
}

function rowContent(msg: Record<string, unknown>, kind: string): string {
  if (kind === 'CONNECTED') {
    const latest = msg.latest_sequence
    const run = msg.agent_run_id
    return `latest_sequence=${String(latest)}  agent_run_id=${run == null ? '—' : String(run)}`
  }
  if (kind === 'ERROR' || kind === 'CLIENT_ERROR') {
    const code = msg.code
    const m = msg.message
    return [typeof code === 'string' ? code : '', typeof m === 'string' ? m : '']
      .filter(Boolean)
      .join(': ')
  }
  if (kind === 'STREAM_END') {
    const st = msg.final_status
    const ec = msg.event_count
    const parts: string[] = []
    if (typeof st === 'string') parts.push(`status: ${st}`)
    if (ec != null && typeof ec === 'object') {
      parts.push(`counts: ${JSON.stringify(ec)}`)
    }
    return parts.join('\n')
  }
  return formatPayloadContent(msg)
}

function rowKey(msg: Record<string, unknown>, index: number): string {
  const id = msg.id
  if (typeof id === 'string' && id.length > 0) return id
  const seq = msg.sequence_number
  if (typeof seq === 'number') return `seq-${seq}`
  const t = msg.type
  if (t === 'CONNECTED') return 'connected'
  if (t === 'STREAM_END') return `stream-end-${index}`
  return `row-${index}`
}

/**
 * Live task thought stream (US10 / T082): scrollable events, colour-coded labels, STREAM_END summary.
 */
export function ThoughtStreamPanel({ taskId, embedded = false }: ThoughtStreamPanelProps) {
  const { events, isConnected, streamEnded, send } = useThoughtStream(taskId)
  const scrollRef = useRef<HTMLDivElement>(null)

  const streamEndPayload = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const m = events[i]
      if (m.type === 'STREAM_END') return m
    }
    return null
  }, [events])

  useLayoutEffect(() => {
    const el = scrollRef.current
    if (el == null) return
    el.scrollTop = el.scrollHeight
  }, [events, streamEnded])

  const showEmpty = taskId == null || taskId === ''

  return (
    <section
      className={embedded ? `${styles.root} ${styles.rootEmbedded}` : styles.root}
      aria-label="Agent thought stream"
    >
      {embedded ? null : (
        <header className={styles.header}>
          <span>Thought stream</span>
          <span className={isConnected ? styles.pillOn : styles.pillOff} title="WebSocket transport">
            {isConnected ? 'Live' : 'Offline'}
          </span>
        </header>
      )}
      {embedded ? (
        <div className={styles.embeddedStatus} aria-live="polite">
          <span className={isConnected ? styles.pillOn : styles.pillOff}>{isConnected ? 'Live' : 'Offline'}</span>
        </div>
      ) : null}
      {!showEmpty ? (
        <PauseResumeControls
          taskId={taskId}
          send={send}
          isConnected={isConnected}
          streamEnded={streamEnded}
          events={events}
        />
      ) : null}
      <div ref={scrollRef} className={embedded ? `${styles.scroller} ${styles.scrollerEmbedded}` : styles.scroller}>
        {showEmpty ? (
          <p className={styles.empty}>
            {embedded ? 'No task selected for this stream.' : 'Open a task in progress to stream agent events.'}
          </p>
        ) : events.length === 0 ? (
          <p className={styles.empty}>Waiting for events…</p>
        ) : (
          events.map((msg, index) => {
            const kind = eventKind(msg)
            return (
              <article key={rowKey(msg, index)} className={styles.row}>
                <div className={styles.rowHeader}>
                  <span className={labelClass(kind)}>{kind}</span>
                  <time className={styles.timestamp} dateTime={typeof msg.timestamp === 'string' ? msg.timestamp : undefined}>
                    {formatTimestamp(msg.timestamp)}
                  </time>
                </div>
                <pre className={styles.content}>{rowContent(msg, kind) || '—'}</pre>
              </article>
            )
          })
        )}
        {streamEnded && streamEndPayload != null ? (
          <div className={styles.summaryBadge} role="status">
            <div className={styles.summaryTitle}>Stream ended</div>
            <div>
              <strong>Final status:</strong> {String(streamEndPayload.final_status ?? '—')}
            </div>
            {streamEndPayload.event_count != null && typeof streamEndPayload.event_count === 'object' ? (
              <div className={styles.summaryGrid}>
                {Object.entries(streamEndPayload.event_count as Record<string, unknown>).map(([k, v]) => (
                  <div key={k} className={styles.summaryItem}>
                    <strong>{k}</strong>: {String(v)}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  )
}
