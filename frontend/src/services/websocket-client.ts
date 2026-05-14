import { getAuthToken } from './api'

const DEFAULT_HTTP_BASE = 'http://localhost:8000'

function normalizeHttpBase(url: string | undefined): string {
  const raw = (url ?? '').trim()
  if (!raw) return DEFAULT_HTTP_BASE
  return raw.replace(/\/$/, '')
}

function httpBaseToWsBase(httpBase: string): string {
  if (httpBase.startsWith('https://')) {
    return `wss://${httpBase.slice('https://'.length)}`
  }
  if (httpBase.startsWith('http://')) {
    return `ws://${httpBase.slice('http://'.length)}`
  }
  return `ws://${httpBase}`
}

export type StreamEventCallback = (message: Record<string, unknown>) => void

export type ConnectionStateCallback = (open: boolean) => void

/**
 * Browser WebSocket client for the task thought stream (`/ws/tasks/{task_id}/stream`).
 * See `specs/001-neo-kanban/contracts/websocket-protocol.md`.
 */
export class TaskThoughtStreamClient {
  private ws: WebSocket | null = null
  private _lastSequence = 0
  private readonly listeners = new Set<StreamEventCallback>()
  private readonly connectionListeners = new Set<ConnectionStateCallback>()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private manualClose = false
  private streamEnded = false

  constructor(
    private readonly taskId: string,
    private readonly getToken: () => string | null = getAuthToken,
    private readonly httpBase: string = normalizeHttpBase(import.meta.env.VITE_API_URL),
  ) {}

  /** Highest `sequence_number` applied from stream payloads (for CATCH_UP). */
  get lastSequence(): number {
    return this._lastSequence
  }

  onEvent(callback: StreamEventCallback): () => void {
    this.listeners.add(callback)
    return () => {
      this.listeners.delete(callback)
    }
  }

  onConnectionChange(callback: ConnectionStateCallback): () => void {
    this.connectionListeners.add(callback)
    return () => {
      this.connectionListeners.delete(callback)
    }
  }

  private notifyConnection(open: boolean): void {
    for (const cb of this.connectionListeners) {
      try {
        cb(open)
      } catch {
        /* ignore */
      }
    }
  }

  private emit(message: Record<string, unknown>): void {
    for (const cb of this.listeners) {
      try {
        cb(message)
      } catch {
        /* consumer error — ignore */
      }
    }
  }

  send(message: string | Record<string, unknown>): void {
    if (this.ws == null || this.ws.readyState !== WebSocket.OPEN) {
      return
    }
    const payload = typeof message === 'string' ? message : JSON.stringify(message)
    this.ws.send(payload)
  }

  connect(): void {
    this.manualClose = false
    this.streamEnded = false
    this.clearReconnectTimer()
    this.openSocket()
  }

  /** Stops auto-reconnect and closes the socket. */
  disconnect(): void {
    this.manualClose = true
    this.clearReconnectTimer()
    if (this.ws != null) {
      this.ws.onclose = null
      this.notifyConnection(false)
      this.ws.close()
      this.ws = null
    }
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer != null) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  private sendCatchUp(): void {
    this.send({ type: 'CATCH_UP', last_sequence: this._lastSequence })
  }

  private buildUrl(token: string): string {
    const wsBase = httpBaseToWsBase(this.httpBase)
    const q = new URLSearchParams({ token })
    return `${wsBase}/ws/tasks/${encodeURIComponent(this.taskId)}/stream?${q.toString()}`
  }

  private openSocket(): void {
    if (this.manualClose || this.streamEnded) {
      return
    }
    const token = this.getToken()
    if (token == null || token === '') {
      this.emit({ type: 'CLIENT_ERROR', code: 'NO_TOKEN', message: 'Missing JWT for WebSocket.' })
      return
    }

    const url = this.buildUrl(token)
    const socket = new WebSocket(url)
    this.ws = socket

    socket.onopen = () => {
      this.notifyConnection(true)
    }

    socket.onmessage = (ev: MessageEvent<string>) => {
      try {
        const msg = JSON.parse(ev.data) as Record<string, unknown>
        this.handleServerMessage(msg)
      } catch {
        /* ignore malformed frame */
      }
    }

    socket.onerror = () => {
      this.emit({ type: 'CLIENT_ERROR', code: 'TRANSPORT', message: 'WebSocket error.' })
    }

    socket.onclose = () => {
      this.notifyConnection(false)
      this.ws = null
      if (this.manualClose || this.streamEnded) {
        return
      }
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null
        this.openSocket()
      }, 1000)
    }
  }

  private handleServerMessage(msg: Record<string, unknown>): void {
    const t = msg.type
    if (t === 'CONNECTED') {
      this.emit(msg)
      this.sendCatchUp()
      return
    }
    if (t === 'STREAM_END') {
      this.streamEnded = true
      this.emit(msg)
      this.disconnect()
      return
    }
    if (t === 'ERROR') {
      this.emit(msg)
      return
    }
    const seq = msg.sequence_number
    if (typeof seq === 'number' && !Number.isNaN(seq)) {
      this._lastSequence = Math.max(this._lastSequence, seq)
    }
    this.emit(msg)
  }
}
