import { useState, useEffect, useCallback } from 'react'
import { usePipelineStore } from '../../stores/pipeline'
import type { Pipeline } from '../../types/pipeline'

// ---------------------------------------------------------------------------
// Save Dialog
// ---------------------------------------------------------------------------

interface SaveDialogProps {
  isOpen: boolean
  onClose: () => void
  initialName: string
  initialDescription: string
  isExisting: boolean
}

function SaveDialog({ isOpen, onClose, initialName, initialDescription, isExisting }: SaveDialogProps) {
  const [name, setName] = useState(initialName)
  const [description, setDescription] = useState(initialDescription)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { savePipeline, createPipeline, updatePipelineMeta } = usePipelineStore()

  useEffect(() => {
    if (isOpen) {
      setName(initialName)
      setDescription(initialDescription)
      setError(null)
    }
  }, [isOpen, initialName, initialDescription])

  const handleSave = useCallback(async () => {
    if (!name.trim()) {
      setError('Pipeline name is required')
      return
    }
    setIsSaving(true)
    setError(null)
    try {
      if (isExisting) {
        updatePipelineMeta({ description })
        // Update name in pipeline before saving
        usePipelineStore.setState((state) => ({
          pipeline: state.pipeline ? { ...state.pipeline, name: name.trim() } : state.pipeline,
        }))
        await savePipeline()
      } else {
        await createPipeline(name.trim(), description)
      }
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setIsSaving(false)
    }
  }, [name, description, isExisting, savePipeline, createPipeline, updatePipelineMeta, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          {isExisting ? 'Save Pipeline' : 'Save Pipeline As'}
        </h2>

        {error && (
          <div className="mb-4 px-3 py-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded text-sm text-red-700 dark:text-red-400">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Pipeline Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Research Pipeline"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this pipeline do?"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm resize-none"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            disabled={isSaving}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving || !name.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? 'Saving...' : isExisting ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Load Dialog
// ---------------------------------------------------------------------------

interface LoadDialogProps {
  isOpen: boolean
  onClose: () => void
}

function LoadDialog({ isOpen, onClose }: LoadDialogProps) {
  const [pipelines, setPipelines] = useState<Pipeline[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [isLoadingPipeline, setIsLoadingPipeline] = useState(false)

  const { listPipelines, loadPipeline } = usePipelineStore()

  useEffect(() => {
    if (!isOpen) return
    setSelectedId(null)
    setError(null)
    setIsLoading(true)
    listPipelines()
      .then((data) => setPipelines(data))
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load pipelines'))
      .finally(() => setIsLoading(false))
  }, [isOpen, listPipelines])

  const handleLoad = useCallback(async () => {
    if (!selectedId) return
    setIsLoadingPipeline(true)
    setError(null)
    try {
      await loadPipeline(selectedId)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load pipeline')
    } finally {
      setIsLoadingPipeline(false)
    }
  }, [selectedId, loadPipeline, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-lg mx-4 p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Load Pipeline
        </h2>

        {error && (
          <div className="mb-4 px-3 py-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded text-sm text-red-700 dark:text-red-400">
            {error}
          </div>
        )}

        <div className="border border-gray-200 dark:border-gray-700 rounded-md overflow-hidden" style={{ minHeight: '200px', maxHeight: '360px', overflowY: 'auto' }}>
          {isLoading ? (
            <div className="flex items-center justify-center h-48 text-sm text-gray-500 dark:text-gray-400">
              Loading pipelines...
            </div>
          ) : pipelines.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-sm text-gray-500 dark:text-gray-400">
              No saved pipelines found
            </div>
          ) : (
            <ul className="divide-y divide-gray-200 dark:divide-gray-700">
              {pipelines.map((p) => (
                <li
                  key={p.id}
                  onClick={() => setSelectedId(p.id)}
                  className={`px-4 py-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 ${
                    selectedId === p.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                        {p.name}
                      </p>
                      {p.metadata.description && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate">
                          {p.metadata.description}
                        </p>
                      )}
                    </div>
                    <span className="ml-3 text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
                      {new Date(p.updatedAt).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                    {p.nodes.length} node{p.nodes.length !== 1 ? 's' : ''} · v{p.version}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-4">
          <button
            onClick={onClose}
            disabled={isLoadingPipeline}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleLoad}
            disabled={!selectedId || isLoadingPipeline}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoadingPipeline ? 'Loading...' : 'Load'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// SaveLoadToolbar — the public component
// ---------------------------------------------------------------------------

export function SaveLoadToolbar() {
  const pipeline = usePipelineStore((s) => s.pipeline)

  const [saveOpen, setSaveOpen] = useState(false)
  const [loadOpen, setLoadOpen] = useState(false)

  const hasId = Boolean(pipeline?.id)
  const currentName = pipeline?.name ?? ''
  const currentDescription = pipeline?.metadata?.description ?? ''

  return (
    <>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setSaveOpen(true)}
          title={hasId ? 'Save pipeline (Ctrl+S)' : 'Save pipeline as new'}
          className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
        >
          {hasId ? 'Save' : 'Save As'}
        </button>
        <button
          onClick={() => setLoadOpen(true)}
          title="Open a saved pipeline"
          className="px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-600 rounded-md transition-colors"
        >
          Open
        </button>
      </div>

      <SaveDialog
        isOpen={saveOpen}
        onClose={() => setSaveOpen(false)}
        initialName={currentName}
        initialDescription={currentDescription}
        isExisting={hasId}
      />
      <LoadDialog
        isOpen={loadOpen}
        onClose={() => setLoadOpen(false)}
      />
    </>
  )
}
