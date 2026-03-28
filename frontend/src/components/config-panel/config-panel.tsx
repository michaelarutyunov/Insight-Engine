import { useEffect, useState, useCallback } from 'react'
import { usePipelineStore } from '../../stores/pipeline'
import { apiClient } from '../../api/client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface JsonSchemaProperty {
  type?: string | string[]
  description?: string
  default?: unknown
  enum?: string[]
  items?: { type?: string }
}

interface JsonSchema {
  type?: string
  properties?: Record<string, JsonSchemaProperty>
  required?: string[]
}

interface BlockInfo {
  block_type: string
  block_implementation: string
  config_schema: JsonSchema
  description: string
  input_schemas: string[]
  output_schemas: string[]
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Resolve the primary type string from a property definition.
 * Handles both `"type": "string"` and `"type": ["string", "null"]`.
 */
function resolveType(prop: JsonSchemaProperty): string {
  if (!prop.type) return 'string'
  if (Array.isArray(prop.type)) {
    return prop.type.find((t) => t !== 'null') ?? 'string'
  }
  return prop.type
}

// ---------------------------------------------------------------------------
// Individual field widgets
// ---------------------------------------------------------------------------

interface FieldProps {
  name: string
  prop: JsonSchemaProperty
  value: unknown
  onChange: (name: string, value: unknown) => void
  required: boolean
}

function FieldWidget({ name, prop, value, onChange, required }: FieldProps) {
  const type = resolveType(prop)
  const label = name.replace(/_/g, ' ')
  const baseInputClass =
    'w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 ' +
    'px-2 py-1.5 text-sm text-gray-900 dark:text-gray-100 ' +
    'focus:outline-none focus:ring-1 focus:ring-blue-500'

  // Enum → select dropdown
  if (prop.enum && prop.enum.length > 0) {
    return (
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-600 dark:text-gray-400 capitalize">
          {label}
          {required && <span className="ml-0.5 text-red-500">*</span>}
        </label>
        {prop.description && (
          <p className="text-[11px] text-gray-500 dark:text-gray-400">{prop.description}</p>
        )}
        <select
          className={baseInputClass}
          value={typeof value === 'string' ? value : (prop.default as string) ?? ''}
          onChange={(e) => onChange(name, e.target.value)}
        >
          <option value="">— select —</option>
          {prop.enum.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </div>
    )
  }

  // Boolean → checkbox/toggle
  if (type === 'boolean') {
    const checked = typeof value === 'boolean' ? value : Boolean(prop.default)
    return (
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-600 dark:text-gray-400 capitalize">
          {label}
          {required && <span className="ml-0.5 text-red-500">*</span>}
        </label>
        {prop.description && (
          <p className="text-[11px] text-gray-500 dark:text-gray-400">{prop.description}</p>
        )}
        <button
          type="button"
          role="switch"
          aria-checked={checked}
          onClick={() => onChange(name, !checked)}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            checked ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
          }`}
        >
          <span
            className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
              checked ? 'translate-x-4' : 'translate-x-0.5'
            }`}
          />
        </button>
      </div>
    )
  }

  // Number / integer → number input
  if (type === 'number' || type === 'integer') {
    return (
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-600 dark:text-gray-400 capitalize">
          {label}
          {required && <span className="ml-0.5 text-red-500">*</span>}
        </label>
        {prop.description && (
          <p className="text-[11px] text-gray-500 dark:text-gray-400">{prop.description}</p>
        )}
        <input
          type="number"
          className={baseInputClass}
          value={typeof value === 'number' ? value : ((prop.default as number) ?? '')}
          step={type === 'integer' ? 1 : 'any'}
          onChange={(e) =>
            onChange(name, type === 'integer' ? parseInt(e.target.value, 10) : parseFloat(e.target.value))
          }
        />
      </div>
    )
  }

  // Array of strings → tag input
  if (type === 'array' && prop.items?.type === 'string') {
    const tags: string[] = Array.isArray(value) ? (value as string[]) : []
    const [draft, setDraft] = useState('')

    const addTag = () => {
      const trimmed = draft.trim()
      if (trimmed && !tags.includes(trimmed)) {
        onChange(name, [...tags, trimmed])
      }
      setDraft('')
    }

    const removeTag = (tag: string) => {
      onChange(name, tags.filter((t) => t !== tag))
    }

    return (
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-600 dark:text-gray-400 capitalize">
          {label}
          {required && <span className="ml-0.5 text-red-500">*</span>}
        </label>
        {prop.description && (
          <p className="text-[11px] text-gray-500 dark:text-gray-400">{prop.description}</p>
        )}
        <div className="flex flex-wrap gap-1 min-h-[28px] rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 p-1">
          {tags.map((tag) => (
            <span
              key={tag}
              className="flex items-center gap-0.5 rounded bg-blue-100 dark:bg-blue-900 px-1.5 py-0.5 text-xs text-blue-800 dark:text-blue-200"
            >
              {tag}
              <button
                type="button"
                onClick={() => removeTag(tag)}
                className="ml-0.5 text-blue-500 hover:text-blue-700 dark:hover:text-blue-300 leading-none"
                aria-label={`Remove ${tag}`}
              >
                ×
              </button>
            </span>
          ))}
          <input
            className="flex-1 min-w-[80px] bg-transparent text-sm text-gray-900 dark:text-gray-100 outline-none"
            placeholder="Add tag, press Enter"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                addTag()
              } else if (e.key === 'Backspace' && draft === '' && tags.length > 0) {
                onChange(name, tags.slice(0, -1))
              }
            }}
          />
        </div>
      </div>
    )
  }

  // Default: string → text input
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-gray-600 dark:text-gray-400 capitalize">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      {prop.description && (
        <p className="text-[11px] text-gray-500 dark:text-gray-400">{prop.description}</p>
      )}
      <input
        type="text"
        className={baseInputClass}
        value={typeof value === 'string' ? value : (prop.default as string) ?? ''}
        onChange={(e) => onChange(name, e.target.value)}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main panel component
// ---------------------------------------------------------------------------

export default function ConfigPanel() {
  const { selectedNodeId, nodes, updateNodeConfig } = usePipelineStore()

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null
  const [blockInfo, setBlockInfo] = useState<BlockInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch block info whenever the selected node changes
  useEffect(() => {
    if (!selectedNode) {
      setBlockInfo(null)
      return
    }

    const { type, blockImplementation } = selectedNode.data
    if (!type || !blockImplementation) {
      setBlockInfo(null)
      return
    }

    setLoading(true)
    setError(null)

    apiClient
      .get<BlockInfo>(`/api/v1/blocks/${type}/${blockImplementation}`)
      .then((info) => {
        setBlockInfo(info)
        setLoading(false)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load block info')
        setLoading(false)
      })
  }, [selectedNode?.id, selectedNode?.data.type, selectedNode?.data.blockImplementation])

  const handleFieldChange = useCallback(
    (fieldName: string, value: unknown) => {
      if (!selectedNodeId) return
      updateNodeConfig(selectedNodeId, { [fieldName]: value })
    },
    [selectedNodeId, updateNodeConfig],
  )

  // Panel is hidden when nothing is selected
  if (!selectedNodeId || !selectedNode) {
    return null
  }

  const config = selectedNode.data.config
  const schema = blockInfo?.config_schema
  const properties = schema?.properties ?? {}
  const required = schema?.required ?? []

  return (
    <aside className="w-72 shrink-0 flex flex-col border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-y-auto">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
          {selectedNode.data.type.replace('_', ' ')}
        </p>
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mt-0.5">
          {selectedNode.data.label || selectedNode.data.blockImplementation}
        </h2>
        {selectedNode.data.description && (
          <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400 leading-snug">
            {selectedNode.data.description}
          </p>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 px-4 py-3">
        {loading && (
          <p className="text-xs text-gray-500 dark:text-gray-400">Loading schema…</p>
        )}

        {error && (
          <p className="text-xs text-red-500">{error}</p>
        )}

        {!loading && !error && Object.keys(properties).length === 0 && (
          <p className="text-xs text-gray-400 dark:text-gray-500 italic">
            This block has no configurable properties.
          </p>
        )}

        {!loading && !error && Object.keys(properties).length > 0 && (
          <div className="flex flex-col gap-4">
            {Object.entries(properties).map(([fieldName, prop]) => (
              <FieldWidget
                key={fieldName}
                name={fieldName}
                prop={prop}
                value={config[fieldName]}
                onChange={handleFieldChange}
                required={required.includes(fieldName)}
              />
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
