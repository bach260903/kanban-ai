import { useEffect, useMemo, useRef, useState } from 'react'

import styles from './pause-resume-controls.module.css'

const IDLE_MS = 30 * 60 * 1000

function deriveAgentPaused(events: Record<string, unknown>[]): boolean {
  let paused = false
  for (const msg of events) {
    if (msg.event_type !== 'STATUS_CHANGE') continue
    const content = msg.content
    if (content == null || typeof content !== 'object') continue
    const c = content as Record<string, unknown>
    if (c.to === 'PAUSED') paused = true
    if (c.from === 'PAUSED' && c.to === 'CODING') paused = false
  }
  return paused
}

export type PauseResumeControlsProps = {
  taskId: string | null
  send: (message: Record<string, unknown> | string) => void
  isConnected: boolean
  streamEnded: boolean
  events: Record<string, unknown>[]
}

/**
 * Pause / resume agent over the thought-stream WebSocket (US11 / T089).
 */
export function PauseResumeControls({
  taskId,
  send,
  isConnected,
  streamEnded,
  events,
}: PauseResumeControlsProps) {
  const [steering, setSteering] = useState('')
  const [idleWarn, setIdleWarn] = useState(false)
  const lastActivityRef = useRef(Date.now())

  const isPaused = useMemo(() => deriveAgentPaused(events), [events])

  useEffect(() => {
    lastActivityRef.current = Date.now()
    setIdleWarn(false)
  }, [events])

  useEffect(() => {
    if (!isConnected || streamEnded || taskId == null || taskId === '') {
      setIdleWarn(false)
      return undefined
    }
    const id = window.setInterval(() => {
      setIdleWarn(Date.now() - lastActivityRef.current >= IDLE_MS)
    }, 30_000)
    return () => window.clearInterval(id)
  }, [isConnected, streamEnded, taskId])

  if (taskId == null || taskId === '' || streamEnded) {
    return null
  }

  const disabled = !isConnected

  const onPause = () => {
    send({ type: 'PAUSE' })
  }

  const onResume = () => {
    const trimmed = steering.trim()
    send({
      type: 'RESUME',
      ...(trimmed.length > 0 ? { steering_instructions: trimmed } : {}),
    })
    setSteering('')
  }

  return (
    <div className={styles.root} role="region" aria-label="Pause and resume agent">
      {idleWarn ? (
        <div className={styles.idleWarning} role="status">
          No stream activity for 30+ minutes. The connection may be idle or the agent may be stalled.
        </div>
      ) : null}
      {!isPaused ? (
        <button type="button" className={styles.pauseBtn} onClick={onPause} disabled={disabled}>
          Pause agent
        </button>
      ) : (
        <div className={styles.resumeBlock}>
          <label htmlFor="pause-resume-steering" className={styles.label}>
            Steering instructions (optional)
          </label>
          <textarea
            id="pause-resume-steering"
            className={styles.textarea}
            value={steering}
            onChange={(e) => setSteering(e.target.value)}
            rows={3}
            maxLength={10_000}
            placeholder="Updated instructions for the coder after resume…"
            disabled={disabled}
          />
          <button type="button" className={styles.resumeBtn} onClick={onResume} disabled={disabled}>
            Resume agent
          </button>
        </div>
      )}
    </div>
  )
}
