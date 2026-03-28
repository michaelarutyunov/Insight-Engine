import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'

import type { PipelineNodeData } from '../../stores/pipeline'

// ---------------------------------------------------------------------------
// Visual style per block type
// ---------------------------------------------------------------------------

const BLOCK_STYLES: Record<string, string> = {
  source:
    'border-blue-400 dark:border-blue-600 bg-blue-50 dark:bg-blue-950',
  transform:
    'border-green-400 dark:border-green-600 bg-green-50 dark:bg-green-950',
  generation:
    'border-purple-400 dark:border-purple-600 bg-purple-50 dark:bg-purple-950',
  evaluation:
    'border-amber-400 dark:border-amber-600 bg-amber-50 dark:bg-amber-950',
  comparator:
    'border-cyan-400 dark:border-cyan-600 bg-cyan-50 dark:bg-cyan-950',
  llm_flex:
    'border-violet-400 dark:border-violet-600 bg-violet-50 dark:bg-violet-950',
  router:
    'border-teal-400 dark:border-teal-600 bg-teal-50 dark:bg-teal-950',
  hitl:
    'border-rose-400 dark:border-rose-600 bg-rose-50 dark:bg-rose-950',
  reporting:
    'border-indigo-400 dark:border-indigo-600 bg-indigo-50 dark:bg-indigo-950',
  sink:
    'border-red-400 dark:border-red-600 bg-red-50 dark:bg-red-950',
}

const BLOCK_BADGE_COLORS: Record<string, string> = {
  source: 'bg-blue-500',
  transform: 'bg-green-500',
  generation: 'bg-purple-500',
  evaluation: 'bg-amber-500',
  comparator: 'bg-cyan-500',
  llm_flex: 'bg-violet-500',
  router: 'bg-teal-500',
  hitl: 'bg-rose-500',
  reporting: 'bg-indigo-500',
  sink: 'bg-red-500',
}

function blockStyle(blockType: string): string {
  return BLOCK_STYLES[blockType] ?? 'border-gray-400 bg-gray-50 dark:bg-gray-900'
}

function badgeColor(blockType: string): string {
  return BLOCK_BADGE_COLORS[blockType] ?? 'bg-gray-500'
}

// ---------------------------------------------------------------------------
// Handle rendering helpers
// ---------------------------------------------------------------------------

const HANDLE_COLORS: Record<string, string> = {
  respondent_collection: '#3b82f6',
  segment_profile_set: '#10b981',
  concept_brief_set: '#8b5cf6',
  evaluation_set: '#f59e0b',
  text_corpus: '#6366f1',
  persona_set: '#ec4899',
  generic_blob: '#6b7280',
}

function handleColor(dataType: string): string {
  return HANDLE_COLORS[dataType] ?? '#6b7280'
}

/**
 * Spread N handles evenly across one side of the node.
 * Returns an array of { id, style } objects.
 */
function spreadHandles(
  ids: string[],
  position: Position,
): Array<{ id: string; style: React.CSSProperties }> {
  const count = ids.length
  if (count === 0) return []

  return ids.map((id, i) => {
    // For 1 handle: 50%. For N handles: evenly distribute from ~15% to ~85%.
    const pct = count === 1 ? 50 : 15 + (i / (count - 1)) * 70
    const isVertical = position === Position.Left || position === Position.Right

    return {
      id,
      style: isVertical
        ? { top: `${pct}%` }
        : { left: `${pct}%` },
    }
  })
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function PipelineNode({ data, selected }: NodeProps) {
  const d = data as PipelineNodeData

  const inputHandles = spreadHandles(d.inputSchema, Position.Left)
  const outputHandles = spreadHandles(d.outputSchema, Position.Right)

  return (
    <div
      className={`
        relative min-w-[200px] max-w-[260px] rounded-lg border-2 px-3 py-2
        shadow-sm transition-shadow
        ${blockStyle(d.type)}
        ${selected ? 'shadow-md ring-2 ring-blue-400 dark:ring-blue-500' : ''}
      `}
    >
      {/* ---- Input handles (left side) ---- */}
      {inputHandles.map((h) => (
        <Handle
          key={h.id}
          type="target"
          position={Position.Left}
          id={h.id}
          style={{
            ...h.style,
            width: 10,
            height: 10,
            background: handleColor(h.id),
            border: '2px solid white',
          }}
        />
      ))}

      {/* ---- Node header ---- */}
      <div className="flex items-center gap-2 mb-1">
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full ${badgeColor(d.type)}`}
        />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          {d.type.replace('_', ' ')}
        </span>
      </div>

      {/* ---- Implementation name (label) ---- */}
      <div className="text-sm font-medium text-gray-900 dark:text-gray-100 leading-tight">
        {d.label || d.blockImplementation}
      </div>

      {/* ---- Description (truncated) ---- */}
      {d.description && (
        <div className="mt-0.5 text-[11px] text-gray-500 dark:text-gray-400 leading-snug line-clamp-2">
          {d.description}
        </div>
      )}

      {/* ---- Output handles (right side) ---- */}
      {outputHandles.map((h) => (
        <Handle
          key={h.id}
          type="source"
          position={Position.Right}
          id={h.id}
          style={{
            ...h.style,
            width: 10,
            height: 10,
            background: handleColor(h.id),
            border: '2px solid white',
          }}
        />
      ))}
    </div>
  )
}

export default memo(PipelineNode)
