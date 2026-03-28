import { useState, useEffect, useCallback, type DragEvent } from 'react'
import { apiClient } from '../../api/client'
import type { BlockCatalogEntry, BlockType } from '../../types/pipeline'

// ---------------------------------------------------------------------------
// Visual config per block type (color + icon label)
// ---------------------------------------------------------------------------

const BLOCK_TYPE_META: Record<
  BlockType,
  { label: string; color: string; bg: string; border: string }
> = {
  source: {
    label: 'Source',
    color: 'text-blue-700 dark:text-blue-300',
    bg: 'bg-blue-100 dark:bg-blue-900/40',
    border: 'border-blue-300 dark:border-blue-700',
  },
  transform: {
    label: 'Transform',
    color: 'text-green-700 dark:text-green-300',
    bg: 'bg-green-100 dark:bg-green-900/40',
    border: 'border-green-300 dark:border-green-700',
  },
  generation: {
    label: 'Generation',
    color: 'text-purple-700 dark:text-purple-300',
    bg: 'bg-purple-100 dark:bg-purple-900/40',
    border: 'border-purple-300 dark:border-purple-700',
  },
  evaluation: {
    label: 'Evaluation',
    color: 'text-orange-700 dark:text-orange-300',
    bg: 'bg-orange-100 dark:bg-orange-900/40',
    border: 'border-orange-300 dark:border-orange-700',
  },
  comparator: {
    label: 'Comparator',
    color: 'text-cyan-700 dark:text-cyan-300',
    bg: 'bg-cyan-100 dark:bg-cyan-900/40',
    border: 'border-cyan-300 dark:border-cyan-700',
  },
  llm_flex: {
    label: 'LLM Flex',
    color: 'text-violet-700 dark:text-violet-300',
    bg: 'bg-violet-100 dark:bg-violet-900/40',
    border: 'border-violet-300 dark:border-violet-700',
  },
  router: {
    label: 'Router',
    color: 'text-amber-700 dark:text-amber-300',
    bg: 'bg-amber-100 dark:bg-amber-900/40',
    border: 'border-amber-300 dark:border-amber-700',
  },
  hitl: {
    label: 'HITL',
    color: 'text-rose-700 dark:text-rose-300',
    bg: 'bg-rose-100 dark:bg-rose-900/40',
    border: 'border-rose-300 dark:border-rose-700',
  },
  reporting: {
    label: 'Reporting',
    color: 'text-teal-700 dark:text-teal-300',
    bg: 'bg-teal-100 dark:bg-teal-900/40',
    border: 'border-teal-300 dark:border-teal-700',
  },
  sink: {
    label: 'Sink',
    color: 'text-red-700 dark:text-red-300',
    bg: 'bg-red-100 dark:bg-red-900/40',
    border: 'border-red-300 dark:border-red-700',
  },
}

// Consistent ordering of block types in the palette
const BLOCK_TYPE_ORDER: BlockType[] = [
  'source',
  'transform',
  'generation',
  'evaluation',
  'comparator',
  'llm_flex',
  'router',
  'hitl',
  'reporting',
  'sink',
]

// ---------------------------------------------------------------------------
// Drag data transfer key
// ---------------------------------------------------------------------------

export const BLOCK_PALETTE_MIME = 'application/x-insight-block'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const BlockPalette = () => {
  const [blocks, setBlocks] = useState<BlockCatalogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [collapsed, setCollapsed] = useState<Set<BlockType>>(new Set())

  // --- Fetch block catalog on mount ---

  useEffect(() => {
    let cancelled = false

    async function fetchBlocks() {
      try {
        const data = await apiClient.get<BlockCatalogEntry[]>('/api/v1/blocks')
        if (!cancelled) {
          setBlocks(data)
          setLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load blocks')
          setLoading(false)
        }
      }
    }

    fetchBlocks()
    return () => {
      cancelled = true
    }
  }, [])

  // --- Toggle group collapse ---

  const toggleGroup = useCallback((blockType: BlockType) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(blockType)) {
        next.delete(blockType)
      } else {
        next.add(blockType)
      }
      return next
    })
  }, [])

  // --- Drag start ---

  const onDragStart = useCallback(
    (event: DragEvent<HTMLDivElement>, entry: BlockCatalogEntry) => {
      const payload = JSON.stringify({
        blockType: entry.block_type,
        implementation: entry.block_implementation,
        description: entry.description,
        inputSchemas: entry.input_schemas,
        outputSchemas: entry.output_schemas,
      })
      event.dataTransfer.setData(BLOCK_PALETTE_MIME, payload)
      event.dataTransfer.effectAllowed = 'move'
    },
    [],
  )

  // --- Group blocks by type in defined order ---

  const grouped = BLOCK_TYPE_ORDER.reduce<
    Record<BlockType, BlockCatalogEntry[]>
  >((acc, bt) => {
    const entries = blocks.filter((b) => b.block_type === bt)
    if (entries.length > 0) acc[bt] = entries
    return acc
  }, {} as Record<BlockType, BlockCatalogEntry[]>)

  // --- Render ---

  return (
    <div className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 h-full flex flex-col">
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">
          Block Palette
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {loading && (
          <p className="text-sm text-gray-500 dark:text-gray-400 px-1 py-2">
            Loading blocks...
          </p>
        )}

        {error && (
          <p className="text-sm text-red-500 dark:text-red-400 px-1 py-2">
            {error}
          </p>
        )}

        {!loading &&
          !error &&
          Object.entries(grouped).map(([blockType, entries]) => {
            const bt = blockType as BlockType
            const meta = BLOCK_TYPE_META[bt]
            const isCollapsed = collapsed.has(bt)

            return (
              <div key={bt} className="mb-1">
                {/* Group header */}
                <button
                  type="button"
                  onClick={() => toggleGroup(bt)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left"
                >
                  <div className={`w-3 h-3 rounded-full ${meta.bg} border ${meta.border}`} />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300 flex-1">
                    {meta.label}
                  </span>
                  <span className="text-xs text-gray-400 dark:text-gray-500">
                    {entries.length}
                  </span>
                  <svg
                    className={`w-3.5 h-3.5 text-gray-400 transition-transform ${isCollapsed ? '' : 'rotate-90'}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </button>

                {/* Block items */}
                {!isCollapsed && (
                  <div className="ml-4 mt-0.5 space-y-0.5">
                    {entries.map((entry) => (
                      <div
                        key={entry.block_implementation}
                        draggable
                        onDragStart={(e) => onDragStart(e, entry)}
                        className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-grab active:cursor-grabbing hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors border border-transparent hover:${meta.border}`}
                        title={entry.description}
                      >
                        <div className={`w-2 h-2 rounded-full ${meta.bg} border ${meta.border}`} />
                        <span className="text-sm text-gray-600 dark:text-gray-400 truncate">
                          {entry.block_implementation}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
      </div>
    </div>
  )
}

export default BlockPalette
