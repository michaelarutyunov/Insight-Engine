export interface BlockConfig {
  [key: string]: unknown
}

export interface Position {
  x: number
  y: number
}

export type BlockType =
  | 'source'
  | 'transform'
  | 'analysis'
  | 'generation'
  | 'evaluation'
  | 'comparator'
  | 'llm_flex'
  | 'router'
  | 'hitl'
  | 'reporting'
  | 'sink'

export interface PipelineNode {
  id: string
  label: string
  type: BlockType
  blockImplementation: string
  description: string
  position: Position
  config: BlockConfig
  inputSchema: string[]
  outputSchema: string[]
}

export interface PipelineEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
  dataType: string
  validated?: boolean
}

export interface PipelineMetadata {
  description: string
  tags: string[]
  author: string
}

export interface Pipeline {
  id: string
  name: string
  version: string
  nodes: PipelineNode[]
  edges: PipelineEdge[]
  metadata: PipelineMetadata
  createdAt: string
  updatedAt: string
}

// ---------------------------------------------------------------------------
// Block catalog (returned by GET /api/v1/blocks)
// ---------------------------------------------------------------------------

export interface BlockCatalogEntry {
  block_type: BlockType
  block_implementation: string
  input_schemas: string[]
  output_schemas: string[]
  config_schema: Record<string, unknown>
  description: string
}