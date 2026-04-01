import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '../../api/client'
import { usePipelineStore } from '../../stores/pipeline'
import type { Pipeline } from '../../types/pipeline'

interface TemplatePickerDialogProps {
  isOpen: boolean
  onClose: () => void
}

function TemplatePickerDialog({ isOpen, onClose }: TemplatePickerDialogProps) {
  const [templates, setTemplates] = useState<Pipeline[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const [isLoadingTemplate, setIsLoadingTemplate] = useState(false)

  const { initEmptyPipeline } = usePipelineStore()

  useEffect(() => {
    if (!isOpen) return
    setSelectedTemplateId(null)
    setError(null)
    setIsLoading(true)
    apiClient
      .get<Pipeline[]>('/api/v1/templates')
      .then((data) => setTemplates(data))
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load templates'))
      .finally(() => setIsLoading(false))
  }, [isOpen])

  const handleSelectTemplate = useCallback(async () => {
    if (!selectedTemplateId) return

    // Check if user selected "Blank Canvas"
    if (selectedTemplateId === 'blank') {
      initEmptyPipeline('New Pipeline', 'Start from scratch')
      onClose()
      return
    }

    setIsLoadingTemplate(true)
    setError(null)
    try {
      // Load the template as a new pipeline (without saving it first)
      const template = await apiClient.get<Pipeline>(`/api/v1/templates/${selectedTemplateId}`)
      // Initialize with template data but remove the template ID so it's treated as new
      const newPipeline: Pipeline = {
        ...template,
        id: '',
        name: `${template.name} (Copy)`,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      }
      usePipelineStore.setState(() => ({
        pipeline: newPipeline,
        nodes: template.nodes.map((node) => ({
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
        })),
        edges: template.edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          sourceHandle: edge.sourceHandle ?? null,
          targetHandle: edge.targetHandle ?? null,
          data: { dataType: edge.dataType, validated: edge.validated ?? false },
        })),
        selectedNodeId: null,
        selectedEdgeId: null,
      }))
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load template')
    } finally {
      setIsLoadingTemplate(false)
    }
  }, [selectedTemplateId, initEmptyPipeline, onClose])

  if (!isOpen) return null

  // Generate a simple text-based pipeline shape description
  const getPipelineShape = (template: Pipeline): string => {
    if (template.nodes.length === 0) return 'Empty pipeline'

    const nodeLabels = template.nodes.map((n) => n.label)
    if (nodeLabels.length <= 3) {
      return nodeLabels.join(' → ')
    }
    return `${nodeLabels[0]} → ${nodeLabels[1]} → ... → ${nodeLabels[nodeLabels.length - 1]}`
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl mx-4 p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          New Pipeline
        </h2>

        {error && (
          <div className="mb-4 px-3 py-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded text-sm text-red-700 dark:text-red-400">
            {error}
          </div>
        )}

        <div className="border border-gray-200 dark:border-gray-700 rounded-md overflow-hidden" style={{ minHeight: '280px', maxHeight: '400px', overflowY: 'auto' }}>
          {isLoading ? (
            <div className="flex items-center justify-center h-64 text-sm text-gray-500 dark:text-gray-400">
              Loading templates...
            </div>
          ) : (
            <ul className="divide-y divide-gray-200 dark:divide-gray-700">
              {/* Blank option */}
              <li
                onClick={() => setSelectedTemplateId('blank')}
                className={`px-4 py-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 ${
                  selectedTemplateId === 'blank' ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
                    <svg className="w-5 h-5 text-gray-500 dark:text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      Blank Canvas
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      Start from scratch with an empty pipeline
                    </p>
                  </div>
                </div>
              </li>

              {/* Template options */}
              {templates.map((template) => (
                <li
                  key={template.id}
                  onClick={() => setSelectedTemplateId(template.id)}
                  className={`px-4 py-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 ${
                    selectedTemplateId === template.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center">
                      <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {template.name}
                      </p>
                      {template.metadata.description && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {template.metadata.description}
                        </p>
                      )}
                      <p className="text-xs text-gray-400 dark:text-gray-500 mt-1 font-mono">
                        {getPipelineShape(template)}
                      </p>
                      {template.metadata.tags && template.metadata.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {template.metadata.tags.map((tag) => (
                            <span
                              key={tag}
                              className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-4">
          <button
            onClick={onClose}
            disabled={isLoadingTemplate}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSelectTemplate}
            disabled={!selectedTemplateId || isLoadingTemplate}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoadingTemplate ? 'Loading...' : selectedTemplateId === 'blank' ? 'Create Blank Pipeline' : 'Use Template'}
          </button>
        </div>
      </div>
    </div>
  )
}

export { TemplatePickerDialog }
