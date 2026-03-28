import { useCallback, useRef, useState, type DragEvent } from 'react'
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

// ---------------------------------------------------------------------------
// Types for connection validation
// ---------------------------------------------------------------------------

interface ConnectionValidationResponse {
  valid: boolean
  reason?: string | null
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
