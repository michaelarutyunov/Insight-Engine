import { useEffect, useRef } from 'react'
import { usePipelineStore } from '../stores/pipeline'

// ---------------------------------------------------------------------------
// Types matching the backend execution status response
// ---------------------------------------------------------------------------

interface NodeStatusEntry {
  status: string
  [key: string]: unknown
}

interface ExecutionStatusResponse {
  run_id: string
  pipeline_id: string
  status: string
  node_statuses: Record<string, NodeStatusEntry>
  hitl_checkpoint?: HitlCheckpoint | null
  [key: string]: unknown
}

export interface HitlCheckpoint {
  node_id: string
  message?: string
  data?: unknown
  [key: string]: unknown
}

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'suspended'])
const POLL_INTERVAL_MS = 2000

/**
 * Polls GET /api/v1/execution/{run_id}/status every 2 seconds.
 * Updates nodeStatuses in the Zustand store.
 * Stops polling when run reaches a terminal state or runId becomes null.
 * Returns the latest status response so callers can react to terminal states.
 */
export function useExecutionPolling(
  runId: string | null,
  onTerminal?: (status: string, response: ExecutionStatusResponse) => void,
): void {
  const setNodeStatuses = usePipelineStore((s) => s.setNodeStatuses)
  const setActiveRunId = usePipelineStore((s) => s.setActiveRunId)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!runId) return

    const poll = async () => {
      try {
        const res = await fetch(
          `http://localhost:8000/api/v1/execution/${runId}/status`,
          { headers: { Accept: 'application/json' } },
        )
        if (!res.ok) return

        const data: ExecutionStatusResponse = (await res.json()) as ExecutionStatusResponse

        // Flatten node_statuses: node_id → status string
        const statuses: Record<string, string> = {}
        for (const [nodeId, entry] of Object.entries(data.node_statuses ?? {})) {
          statuses[nodeId] = entry.status
        }
        setNodeStatuses(statuses)

        if (TERMINAL_STATUSES.has(data.status)) {
          if (intervalRef.current !== null) {
            clearInterval(intervalRef.current)
            intervalRef.current = null
          }
          if (data.status !== 'suspended') {
            setActiveRunId(null)
          }
          onTerminal?.(data.status, data)
        }
      } catch {
        // Network errors are ignored; polling continues
      }
    }

    // Poll immediately, then on interval
    void poll()
    intervalRef.current = setInterval(() => { void poll() }, POLL_INTERVAL_MS)

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [runId, setNodeStatuses, setActiveRunId, onTerminal])
}
