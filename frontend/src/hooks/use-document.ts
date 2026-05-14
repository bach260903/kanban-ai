import { useCallback, useEffect, useRef, useState } from 'react'

import type { AgentRun, Document } from '../types'

import { getAgentRun, getDocument } from '../services/document-api'

const POLL_INTERVAL_MS = 3000

function isGeneratingStatus(status: AgentRun['status'] | undefined): boolean {
  return status === 'running'
}

export type UseDocumentOptions = {
  /**
   * When set, the hook polls this agent run every 3s while status is ``running``,
   * then refetches the document once generation finishes.
   */
  agentRunId?: string | null
}

export type UseDocumentResult = {
  document: Document | null
  agentRun: AgentRun | null
  /** True while the linked agent run is ``running`` (e.g. SPEC generation in flight). */
  isGenerating: boolean
  isLoading: boolean
  error: Error | null
  refetch: () => Promise<void>
}

export function useDocument(
  projectId: string | undefined,
  documentId: string | undefined,
  options?: UseDocumentOptions,
): UseDocumentResult {
  const agentRunId = options?.agentRunId ?? null
  const [document, setDocument] = useState<Document | null>(null)
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const clearPoll = useCallback(() => {
    if (pollRef.current != null) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const loadDocument = useCallback(async () => {
    if (!projectId || !documentId) {
      setDocument(null)
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const doc = await getDocument(projectId, documentId)
      setDocument(doc)
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)))
      setDocument(null)
    } finally {
      setIsLoading(false)
    }
  }, [projectId, documentId])

  useEffect(() => {
    void loadDocument()
  }, [loadDocument])

  useEffect(() => {
    clearPoll()
    if (!agentRunId) {
      setAgentRun(null)
      return
    }

    let cancelled = false

    const tick = async (): Promise<AgentRun | null> => {
      try {
        const run = await getAgentRun(agentRunId)
        if (cancelled) return null
        setAgentRun(run)
        if (!isGeneratingStatus(run.status)) {
          clearPoll()
          await loadDocument()
        }
        return run
      } catch (e) {
        if (cancelled) return null
        setError(e instanceof Error ? e : new Error(String(e)))
        clearPoll()
        return null
      }
    }

    void (async () => {
      const run = await tick()
      if (cancelled || !run) return
      if (isGeneratingStatus(run.status)) {
        pollRef.current = setInterval(() => {
          void tick()
        }, POLL_INTERVAL_MS)
      }
    })()

    return () => {
      cancelled = true
      clearPoll()
    }
  }, [agentRunId, clearPoll, loadDocument])

  const isGenerating = isGeneratingStatus(agentRun?.status)

  return {
    document,
    agentRun,
    isGenerating,
    isLoading,
    error,
    refetch: loadDocument,
  }
}
