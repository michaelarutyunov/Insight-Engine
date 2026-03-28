import { create } from 'zustand'
import {
  applyNodeChanges,
  applyEdgeChanges,
  type NodeChange,
  type EdgeChange,
  type Node,
  type Edge,
} from '@xyflow/react'

import { apiClient } from '../api/client'
import type {
  Pipeline,
  PipelineNode,
  PipelineEdge,
  PipelineMetadata,
} from '../types/pipeline'

// ---------------------------------------------------------------------------
// Our custom data shape stored inside each React Flow Node.data
// ---------------------------------------------------------------------------

export interface PipelineNodeData extends Record<string, unknown> {
  label: string
  type: string
  blockImplementation: string
  description: string
  config: Record<string, unknown>
  inputSchema: string[]
  outputSchema: string[]
}

// ---------------------------------------------------------------------------
// Helpers: convert between our domain models and React Flow node/edge shapes
// ---------------------------------------------------------------------------

function pipelineNodeToReactFlow(node: PipelineNode): Node<PipelineNodeData> {
  return {
    id: node.id,
    type: 'pipelineNode',
    position: { x: node.position.x, y: node.position.y },
    data: {
      label: node.label,
      type: node.type,
      blockImplementation: node.blockImplementation,
      description: node.description,
      config: { ...node.config },
      inputSchema: [...node.inputSchema],
      outputSchema: [...node.outputSchema],
    },
  }
}

function reactFlowNodeToPipelineNode(rfNode: Node<PipelineNodeData>): PipelineNode {
  return {
    id: rfNode.id,
    label: rfNode.data.label,
    type: rfNode.data.type as PipelineNode['type'],
    blockImplementation: rfNode.data.blockImplementation,
    description: rfNode.data.description,
    position: { ...rfNode.position },
    config: { ...rfNode.data.config },
    inputSchema: [...rfNode.data.inputSchema],
    outputSchema: [...rfNode.data.outputSchema],
  }
}

function pipelineEdgeToReactFlow(edge: PipelineEdge): Edge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle ?? null,
    targetHandle: edge.targetHandle ?? null,
    data: { dataType: edge.dataType, validated: edge.validated },
  }
}

function reactFlowEdgeToPipelineEdge(rfEdge: Edge): PipelineEdge {
  return {
    id: rfEdge.id,
    source: rfEdge.source,
    target: rfEdge.target,
    sourceHandle: rfEdge.sourceHandle ?? undefined,
    targetHandle: rfEdge.targetHandle ?? undefined,
    dataType: (rfEdge.data as { dataType?: string } | undefined)?.dataType ?? '',
    validated: (rfEdge.data as { validated?: boolean } | undefined)?.validated,
  }
}

// ---------------------------------------------------------------------------
// Store interface
// ---------------------------------------------------------------------------

interface PipelineStore {
  // --- state ---
  pipeline: Pipeline | null
  nodes: Node<PipelineNodeData>[]
  edges: Edge[]
  selectedNodeId: string | null
  selectedEdgeId: string | null
  isLoading: boolean
  error: string | null

  // --- React Flow controlled-mode handlers ---
  onNodesChange: (changes: NodeChange<Node<PipelineNodeData>>[]) => void
  onEdgesChange: (changes: EdgeChange<Edge>[]) => void

  // --- selection ---
  setSelectedNode: (nodeId: string | null) => void
  setSelectedEdge: (edgeId: string | null) => void

  // --- node mutations ---
  addNode: (node: PipelineNode) => void
  updateNodeConfig: (nodeId: string, config: Record<string, unknown>) => void
  removeNode: (nodeId: string) => void

  // --- edge mutations ---
  addEdge: (edge: PipelineEdge) => void
  removeEdge: (edgeId: string) => void

  // --- pipeline-level mutations ---
  updatePipelineMeta: (meta: Partial<PipelineMetadata>) => void

  // --- async API operations ---
  loadPipeline: (pipelineId: string) => Promise<void>
  savePipeline: () => Promise<void>
  createPipeline: (name: string, description: string) => Promise<Pipeline>
  listPipelines: () => Promise<Pipeline[]>
  initEmptyPipeline: (name: string, description: string) => void
}

// ---------------------------------------------------------------------------
// Store implementation
// ---------------------------------------------------------------------------

function syncPipelineFromReactFlow(
  pipeline: Pipeline | null,
  nodes: Node<PipelineNodeData>[],
  edges: Edge[]
): Pipeline | null {
  if (!pipeline) return null
  return {
    ...pipeline,
    nodes: nodes.map(reactFlowNodeToPipelineNode),
    edges: edges.map(reactFlowEdgeToPipelineEdge),
    updatedAt: new Date().toISOString(),
  }
}

export const usePipelineStore = create<PipelineStore>((set, get) => ({
  pipeline: null,
  nodes: [],
  edges: [],
  selectedNodeId: null,
  selectedEdgeId: null,
  isLoading: false,
  error: null,

  // -----------------------------------------------------------------------
  // React Flow controlled-mode handlers
  // -----------------------------------------------------------------------

  onNodesChange: (changes) => {
    set((state) => {
      const updatedNodes = applyNodeChanges(changes, state.nodes)
      return {
        nodes: updatedNodes,
        pipeline: syncPipelineFromReactFlow(state.pipeline, updatedNodes, state.edges),
      }
    })
  },

  onEdgesChange: (changes) => {
    set((state) => {
      const updatedEdges = applyEdgeChanges(changes, state.edges)
      return {
        edges: updatedEdges,
        pipeline: syncPipelineFromReactFlow(state.pipeline, state.nodes, updatedEdges),
      }
    })
  },

  // -----------------------------------------------------------------------
  // Selection
  // -----------------------------------------------------------------------

  setSelectedNode: (nodeId) => set({ selectedNodeId: nodeId, selectedEdgeId: null }),

  setSelectedEdge: (edgeId) => set({ selectedEdgeId: edgeId, selectedNodeId: null }),

  // -----------------------------------------------------------------------
  // Node mutations
  // -----------------------------------------------------------------------

  addNode: (node) => {
    const rfNode = pipelineNodeToReactFlow(node)
    set((state) => {
      const updatedNodes = [...state.nodes, rfNode]
      return {
        nodes: updatedNodes,
        pipeline: syncPipelineFromReactFlow(state.pipeline, updatedNodes, state.edges),
      }
    })
  },

  updateNodeConfig: (nodeId, config) => {
    set((state) => {
      const updatedNodes = state.nodes.map((n) =>
        n.id === nodeId
          ? { ...n, data: { ...n.data, config: { ...n.data.config, ...config } } }
          : n
      )
      return {
        nodes: updatedNodes,
        pipeline: syncPipelineFromReactFlow(state.pipeline, updatedNodes, state.edges),
      }
    })
  },

  removeNode: (nodeId) => {
    set((state) => {
      const updatedNodes = state.nodes.filter((n) => n.id !== nodeId)
      const updatedEdges = state.edges.filter(
        (e) => e.source !== nodeId && e.target !== nodeId
      )
      return {
        nodes: updatedNodes,
        edges: updatedEdges,
        selectedNodeId: state.selectedNodeId === nodeId ? null : state.selectedNodeId,
        pipeline: syncPipelineFromReactFlow(state.pipeline, updatedNodes, updatedEdges),
      }
    })
  },

  // -----------------------------------------------------------------------
  // Edge mutations
  // -----------------------------------------------------------------------

  addEdge: (edge) => {
    const rfEdge = pipelineEdgeToReactFlow(edge)
    set((state) => {
      const updatedEdges = [...state.edges, rfEdge]
      return {
        edges: updatedEdges,
        pipeline: syncPipelineFromReactFlow(state.pipeline, state.nodes, updatedEdges),
      }
    })
  },

  removeEdge: (edgeId) => {
    set((state) => {
      const updatedEdges = state.edges.filter((e) => e.id !== edgeId)
      return {
        edges: updatedEdges,
        selectedEdgeId: state.selectedEdgeId === edgeId ? null : state.selectedEdgeId,
        pipeline: syncPipelineFromReactFlow(state.pipeline, state.nodes, updatedEdges),
      }
    })
  },

  // -----------------------------------------------------------------------
  // Pipeline-level mutations
  // -----------------------------------------------------------------------

  updatePipelineMeta: (meta) => {
    set((state) => {
      if (!state.pipeline) return state
      return {
        pipeline: {
          ...state.pipeline,
          metadata: { ...state.pipeline.metadata, ...meta },
          updatedAt: new Date().toISOString(),
        },
      }
    })
  },

  // -----------------------------------------------------------------------
  // Async API operations
  // -----------------------------------------------------------------------

  loadPipeline: async (pipelineId) => {
    set({ isLoading: true, error: null })
    try {
      const data = await apiClient.get<Pipeline>(
        `/api/v1/pipelines/${pipelineId}`
      )
      set({
        pipeline: data,
        nodes: data.nodes.map(pipelineNodeToReactFlow),
        edges: data.edges.map(pipelineEdgeToReactFlow),
        selectedNodeId: null,
        selectedEdgeId: null,
        isLoading: false,
      })
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to load pipeline',
      })
    }
  },

  savePipeline: async () => {
    const { pipeline } = get()
    if (!pipeline) {
      set({ error: 'No pipeline loaded' })
      return
    }

    set({ isLoading: true, error: null })
    try {
      const now = new Date().toISOString()
      const syncedPipeline = syncPipelineFromReactFlow(pipeline, get().nodes, get().edges)
      const payload = { ...syncedPipeline, updatedAt: now }
      const updated = await apiClient.put<Pipeline>(`/api/v1/pipelines/${pipeline.id}`, payload)
      set({ isLoading: false, pipeline: updated })
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to save pipeline',
      })
    }
  },

  createPipeline: async (name: string, description: string) => {
    const { nodes, edges } = get()
    set({ isLoading: true, error: null })
    try {
      const payload = {
        name,
        nodes: nodes.map(reactFlowNodeToPipelineNode),
        edges: edges.map(reactFlowEdgeToPipelineEdge),
        metadata: { description, tags: [], author: '' },
      }
      const created = await apiClient.post<Pipeline>('/api/v1/pipelines', payload)
      set({ isLoading: false, pipeline: created })
      return created
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to create pipeline',
      })
      throw err
    }
  },

  listPipelines: async () => {
    const data = await apiClient.get<Pipeline[]>('/api/v1/pipelines')
    return data
  },

  initEmptyPipeline: (name: string, description: string) => {
    const now = new Date().toISOString()
    const newPipeline: Pipeline = {
      id: '',
      name,
      version: '1.0.0',
      nodes: [],
      edges: [],
      metadata: { description, tags: [], author: '' },
      createdAt: now,
      updatedAt: now,
    }
    set({ pipeline: newPipeline, nodes: [], edges: [], selectedNodeId: null, selectedEdgeId: null })
  },
}))
