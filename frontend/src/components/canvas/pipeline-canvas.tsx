import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Controls,
  Background,
  BackgroundVariant,
  MiniMap,
  useReactFlow,
  type Connection,
  type NodeTypes,
  type Node,
  type Edge,
  type IsValidConnection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import PipelineNodeComponent from './pipeline-node'
import { usePipelineStore, type PipelineNodeData } from '../../stores/pipeline'
import type { PipelineNode } from '../../types/pipeline'
import { apiClient } from '../../api/client'
import { useExecutionPolling, type HitlCheckpoint } from '../../hooks/useExecutionPolling'

// ---------------------------------------------------------------------------
// Types for connection validation and execution
// ---------------------------------------------------------------------------

interface ConnectionValidationResponse {
  valid: boolean
  reason?: string | null
}

interface RunPipelineResponse {
  run_id: string
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// Custom node type registry (stable reference)
// ---------------------------------------------------------------------------

const nodeTypes: NodeTypes = {
  pipelineNode: PipelineNodeComponent,
}

// ---------------------------------------------------------------------------
// Inner canvas — must be inside <ReactFlowProvider> for useReactFlow()
// ---------------------------------------------------------------------------

function PipelineCanvasInner() {
  const store = usePipelineStore()
  const { screenToFlowPosition } = useReactFlow()

  // ---- Connection validation state ---------------------------------------

  // Tracks whether the current in-progress connection is valid/invalid/unknown
  const [connectionValidity, setConnectionValidity] = useState<'valid' | 'invalid' | null>(null)
  // Error tooltip message for invalid connections
  const [errorTooltip, setErrorTooltip] = useState<string | null>(null)

  useEffect(() => {
    if (!errorTooltip) return
    const timer = setTimeout(() => setErrorTooltip(null), 3000)
    return () => clearTimeout(timer)
  }, [errorTooltip])

  // ---- Execution state ---------------------------------------------------

  const [isRunning, setIsRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [hitlCheckpoint, setHitlCheckpoint] = useState<HitlCheckpoint | null>(null)
  const [hitlResponse, setHitlResponse] = useState('')
  const [hitlSubmitting, setHitlSubmitting] = useState(false)

  // Show success notification, then clear after 4s
  useEffect(() => {
    if (!successMessage) return
    const timer = setTimeout(() => setSuccessMessage(null), 4000)
    return () => clearTimeout(timer)
  }, [successMessage])

  const onTerminal = useCallback(
    (status: string, response: { hitl_checkpoint?: HitlCheckpoint | null }) => {
      setIsRunning(false)
      if (status === 'completed') {
        setSuccessMessage('Pipeline completed successfully.')
        store.setNodeStatuses({})
      } else if (status === 'failed') {
        setRunError('Pipeline run failed. Check node status indicators for details.')
      } else if (status === 'suspended') {
        const checkpoint = response.hitl_checkpoint ?? null
        setHitlCheckpoint(checkpoint)
      }
    },
    [store],
  )

  useExecutionPolling(store.activeRunId, onTerminal)

  const handleRunPipeline = useCallback(async () => {
    const pipelineId = store.pipeline?.id
    if (!pipelineId) {
      setRunError('No pipeline loaded. Save the pipeline first.')
      return
    }
    setIsRunning(true)
    setRunError(null)
    setSuccessMessage(null)
    setHitlCheckpoint(null)
    store.setNodeStatuses({})

    try {
      const res = await apiClient.post<RunPipelineResponse>(
        `/api/v1/execution/${pipelineId}/run`,
        {},
      )
      store.setActiveRunId(res.run_id)
    } catch (err) {
      setIsRunning(false)
      setRunError(err instanceof Error ? err.message : 'Failed to start pipeline run.')
    }
  }, [store])

  const handleHitlSubmit = useCallback(async () => {
    if (!store.activeRunId) return
    setHitlSubmitting(true)
    try {
      await apiClient.post(`/api/v1/hitl/${store.activeRunId}/respond`, {
        response: hitlResponse,
      })
      setHitlCheckpoint(null)
      setHitlResponse('')
      setIsRunning(true)
      // Restart polling by refreshing activeRunId to trigger hook re-run
      const runId = store.activeRunId
      store.setActiveRunId(null)
      setTimeout(() => store.setActiveRunId(runId), 50)
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Failed to submit HITL response.')
    } finally {
      setHitlSubmitting(false)
    }
  }, [store, hitlResponse])

  // Ref to debounce rapid isValidConnection calls
  const validationCache = useRef<Map<string, boolean>>(new Map())

  // ---- Drag-and-drop from palette ----------------------------------------

  const onDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault()

      // Must match the MIME type set by BlockPalette
      const raw = event.dataTransfer.getData('application/x-insight-block')
      if (!raw) return

      let blockData: {
        blockType?: string
        implementation?: string
        description?: string
        inputSchemas?: string[]
        outputSchemas?: string[]
      }
      try {
        blockData = JSON.parse(raw)
      } catch {
        return
      }

      // Convert screen coordinates to flow coordinates
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })

      // Build a PipelineNode from the dragged data
      const newNode: PipelineNode = {
        id: `node-${Date.now()}`,
        label: blockData.implementation ?? 'Untitled',
        type: (blockData.blockType as PipelineNode['type']) ?? 'transform',
        blockImplementation: blockData.implementation ?? '',
        description: blockData.description ?? '',
        position,
        config: {},
        inputSchema: blockData.inputSchemas ?? [],
        outputSchema: blockData.outputSchemas ?? [],
      }

      store.addNode(newNode)
    },
    [screenToFlowPosition, store],
  )

  // ---- Edge creation via connection --------------------------------------

  /**
   * Build the validation payload from a Connection and the current node list.
   * Returns null if required node data is missing.
   */
  const buildValidationPayload = useCallback(
    (params: Connection | Edge) => {
      if (!params.source || !params.target) return null

      const sourceNode = store.nodes.find((n) => n.id === params.source)
      const targetNode = store.nodes.find((n) => n.id === params.target)
      if (!sourceNode || !targetNode) return null

      // The data_type comes from the source port (sourceHandle) or falls back to
      // the first entry of the source's outputSchema.
      const dataType =
        params.sourceHandle ||
        sourceNode.data.outputSchema[0] ||
        'generic_blob'

      return {
        source_block_type: sourceNode.data.type,
        source_block_implementation: sourceNode.data.blockImplementation,
        source_port: params.sourceHandle ?? 'output',
        target_block_type: targetNode.data.type,
        target_block_implementation: targetNode.data.blockImplementation,
        target_port: params.targetHandle ?? 'input',
        data_type: dataType,
      }
    },
    [store.nodes],
  )

  /**
   * isValidConnection — called synchronously by React Flow during drag.
   * We use a cache populated by an async pre-check so the sync callback
   * can return an answer without blocking.  First call for a new pair
   * optimistically returns true while the API call populates the cache.
   */
  const isValidConnection = useCallback<IsValidConnection>(
    (params): boolean => {
      if (!params.source || !params.target) return false

      const cacheKey = `${params.source}:${params.sourceHandle ?? ''}→${params.target}:${params.targetHandle ?? ''}`
      if (validationCache.current.has(cacheKey)) {
        return validationCache.current.get(cacheKey)!
      }

      // Fire-and-forget: populate cache for subsequent hover events
      const payload = buildValidationPayload(params)
      if (payload) {
        apiClient
          .post<ConnectionValidationResponse>(
            '/api/v1/pipelines/validate-connection',
            payload,
          )
          .then((res) => {
            validationCache.current.set(cacheKey, res.valid)
            setConnectionValidity(res.valid ? 'valid' : 'invalid')
            if (!res.valid) {
              setErrorTooltip(res.reason ?? 'Connection not allowed')
            } else {
              setErrorTooltip(null)
            }
          })
          .catch(() => {
            // Network error — allow the connection; server will validate on save
            validationCache.current.set(cacheKey, true)
          })
      }

      // Optimistic: allow while we wait for the first API response
      return true
    },
    [buildValidationPayload],
  )

  /**
   * onConnect — fires when user releases the drag and confirms the connection.
   * We call the API one final time to get the data_type and validated flag,
   * then add the edge to the store.
   */
  const onConnect = useCallback(
    async (params: Connection) => {
      if (!params.source || !params.target) return

      const payload = buildValidationPayload(params)
      const dataType = payload?.data_type ?? 'generic_blob'

      let validated = false
      if (payload) {
        try {
          const res = await apiClient.post<ConnectionValidationResponse>(
            '/api/v1/pipelines/validate-connection',
            payload,
          )
          if (!res.valid) {
            setErrorTooltip(res.reason ?? 'Connection not allowed')
            setConnectionValidity('invalid')
            // Clear the tooltip after 3 s
            setTimeout(() => {
              setErrorTooltip(null)
              setConnectionValidity(null)
            }, 3000)
            return
          }
          validated = res.valid
          setErrorTooltip(null)
          setConnectionValidity('valid')
          setTimeout(() => setConnectionValidity(null), 1500)
        } catch {
          // Network error — allow optimistically
          validated = false
        }
      }

      // Clear validation cache entry so future drags re-validate
      const cacheKey = `${params.source}:${params.sourceHandle ?? ''}→${params.target}:${params.targetHandle ?? ''}`
      validationCache.current.delete(cacheKey)

      store.addEdge({
        id: `e-${params.source}-${params.sourceHandle ?? 'out'}-${params.target}-${params.targetHandle ?? 'in'}`,
        source: params.source,
        target: params.target,
        sourceHandle: params.sourceHandle ?? undefined,
        targetHandle: params.targetHandle ?? undefined,
        dataType,
        validated,
      })
    },
    [store, buildValidationPayload],
  )

  // ---- Clear connection state when drag ends without connecting ----------

  const onConnectEnd = useCallback(() => {
    setConnectionValidity(null)
  }, [])

  // ---- Selection ---------------------------------------------------------

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node<PipelineNodeData>) => {
      store.setSelectedNode(node.id)
    },
    [store],
  )

  const onEdgeClick = useCallback(
    (_event: React.MouseEvent, edge: Edge) => {
      store.setSelectedEdge(edge.id)
    },
    [store],
  )

  // ---- Deletion ----------------------------------------------------------

  const onNodesDelete = useCallback(
    (deleted: Node<PipelineNodeData>[]) => {
      for (const node of deleted) {
        store.removeNode(node.id)
      }
    },
    [store],
  )

  const onEdgesDelete = useCallback(
    (deleted: Edge[]) => {
      for (const edge of deleted) {
        store.removeEdge(edge.id)
      }
    },
    [store],
  )

  // ---- Pane click (deselect) ---------------------------------------------

  const onPaneClick = useCallback(() => {
    store.setSelectedNode(null)
    store.setSelectedEdge(null)
  }, [store])

  // ---- MiniMap node colour -----------------------------------------------

  const miniMapNodeColor = useCallback((node: Node<PipelineNodeData>) => {
    const colors: Record<string, string> = {
      source: '#3b82f6',
      transform: '#22c55e',
      generation: '#a855f7',
      evaluation: '#f59e0b',
      comparator: '#06b6d4',
      llm_flex: '#8b5cf6',
      router: '#14b8a6',
      hitl: '#f43f5e',
      reporting: '#6366f1',
      sink: '#ef4444',
    }
    return colors[node.data?.type] ?? '#6b7280'
  }, [])

  // ---- Render ------------------------------------------------------------

  // ---- Connection line style changes colour during drag -----------------

  const connectionLineStyle: React.CSSProperties =
    connectionValidity === 'invalid'
      ? { stroke: '#ef4444', strokeWidth: 2 }
      : connectionValidity === 'valid'
        ? { stroke: '#22c55e', strokeWidth: 2 }
        : { stroke: '#6366f1', strokeWidth: 2 }

  // ---- Edge default styles (valid edges: green, unvalidated: default) ---

  const defaultEdgeOptions = {
    style: { strokeWidth: 2 },
  }

  return (
    <div className="relative h-full w-full">
      <ReactFlow
        nodes={store.nodes}
        edges={store.edges}
        onNodesChange={store.onNodesChange}
        onEdgesChange={store.onEdgesChange}
        onConnect={onConnect}
        onConnectEnd={onConnectEnd}
        isValidConnection={isValidConnection}
        connectionLineStyle={connectionLineStyle}
        defaultEdgeOptions={defaultEdgeOptions}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onNodesDelete={onNodesDelete}
        onEdgesDelete={onEdgesDelete}
        onPaneClick={onPaneClick}
        onDragOver={onDragOver}
        onDrop={onDrop}
        nodeTypes={nodeTypes}
        fitView
        deleteKeyCode={['Backspace', 'Delete']}
        className="bg-gray-50 dark:bg-gray-900"
      >
        <Controls position="top-right" />
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
        <MiniMap
          nodeColor={miniMapNodeColor}
          maskColor="rgba(0, 0, 0, 0.08)"
          className="!bg-white dark:!bg-gray-800"
        />
      </ReactFlow>

      {/* ---- Run Pipeline toolbar button ---- */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
        <button
          onClick={() => { void handleRunPipeline() }}
          disabled={isRunning || !store.pipeline?.id}
          className={`
            flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium shadow
            transition-colors
            ${isRunning
              ? 'cursor-not-allowed bg-blue-400 text-white'
              : 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800'
            }
            disabled:opacity-60
          `}
          aria-label="Run pipeline"
        >
          {isRunning ? (
            <>
              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Running…
            </>
          ) : (
            <>
              <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
              </svg>
              Run Pipeline
            </>
          )}
        </button>
      </div>

      {/* Error tooltip shown when a connection is rejected */}
      {errorTooltip && (
        <div
          className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white shadow-lg"
          role="alert"
          aria-live="assertive"
        >
          {errorTooltip}
        </div>
      )}

      {/* Run error notification */}
      {runError && (
        <div
          className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-lg"
          role="alert"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
          {runError}
          <button
            className="ml-2 opacity-75 hover:opacity-100"
            onClick={() => setRunError(null)}
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      )}

      {/* Success notification */}
      {successMessage && (
        <div
          className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white shadow-lg"
          role="status"
          aria-live="polite"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          {successMessage}
        </div>
      )}

      {/* HITL review modal */}
      {hitlCheckpoint && (
        <div
          className="absolute inset-0 z-30 flex items-center justify-center bg-black/40"
          role="dialog"
          aria-modal="true"
          aria-labelledby="hitl-modal-title"
        >
          <div className="w-full max-w-md rounded-xl bg-white dark:bg-gray-800 p-6 shadow-2xl">
            <h2 id="hitl-modal-title" className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">
              Human Review Required
            </h2>
            {hitlCheckpoint.message && (
              <p className="text-sm text-gray-600 dark:text-gray-300 mb-3">
                {hitlCheckpoint.message}
              </p>
            )}
            {hitlCheckpoint.data !== undefined && (
              <pre className="mb-3 max-h-40 overflow-auto rounded-md bg-gray-100 dark:bg-gray-900 p-3 text-xs text-gray-700 dark:text-gray-300">
                {JSON.stringify(hitlCheckpoint.data, null, 2)}
              </pre>
            )}
            <label htmlFor="hitl-response" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Your response
            </label>
            <textarea
              id="hitl-response"
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows={4}
              value={hitlResponse}
              onChange={(e) => setHitlResponse(e.target.value)}
              placeholder="Enter your review or approval…"
            />
            <div className="mt-3 flex justify-end gap-2">
              <button
                className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                onClick={() => setHitlCheckpoint(null)}
                disabled={hitlSubmitting}
              >
                Dismiss
              </button>
              <button
                className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
                onClick={() => { void handleHitlSubmit() }}
                disabled={hitlSubmitting || hitlResponse.trim() === ''}
              >
                {hitlSubmitting ? 'Submitting…' : 'Submit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Exported wrapper — ensures ReactFlowProvider wraps the canvas
// ---------------------------------------------------------------------------

export default function PipelineCanvas() {
  return (
    <ReactFlowProvider>
      <PipelineCanvasInner />
    </ReactFlowProvider>
  )
}
