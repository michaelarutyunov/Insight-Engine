/**
 * ChatPanel -- slide-in drawer for the research assistant and co-pilot chat.
 *
 * Displays message history with streaming token rendering,
 * provides a text input box with send button, and renders
 * a co-pilot diff preview with confirm/reject buttons.
 */
import { useRef, useEffect } from 'react'
import { useChatStore } from '../../stores/chat'
import type { PipelineDiff } from '../../stores/chat'

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ModeSelector() {
  const mode = useChatStore((s) => s.mode)
  const setMode = useChatStore((s) => s.setMode)

  return (
    <div className="flex gap-1 px-4 pb-2">
      <button
        onClick={() => setMode('assistant')}
        className={`flex-1 text-xs px-3 py-1.5 rounded-md font-medium transition-colors ${
          mode === 'assistant'
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
        }`}
      >
        Assistant
      </button>
      <button
        onClick={() => setMode('copilot')}
        className={`flex-1 text-xs px-3 py-1.5 rounded-md font-medium transition-colors ${
          mode === 'copilot'
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
        }`}
      >
        Co-pilot
      </button>
    </div>
  )
}

function MessageList() {
  const messages = useChatStore((s) => s.messages)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const currentStreamingContent = useChatStore((s) => s.currentStreamingContent)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentStreamingContent])

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`px-3 py-2 rounded-lg text-sm whitespace-pre-wrap break-words ${
            msg.role === 'user'
              ? 'bg-blue-600 text-white ml-6'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-gray-100 mr-6'
          }`}
        >
          <div className="text-xs font-semibold mb-1 opacity-70">
            {msg.role === 'user' ? 'You' : 'Assistant'}
          </div>
          {msg.content}
        </div>
      ))}

      {/* Streaming indicator */}
      {isStreaming && currentStreamingContent === '' && (
        <div className="px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-700 mr-6">
          <div className="text-xs font-semibold mb-1 opacity-70">Assistant</div>
          <span className="inline-block h-2 w-2 bg-gray-400 rounded-full animate-pulse" />
          <span className="text-sm text-gray-500 ml-2">Thinking...</span>
        </div>
      )}

      <div ref={endRef} />
    </div>
  )
}

function CopilotDiffPreview({ diff }: { diff: PipelineDiff }) {
  return (
    <div className="mx-4 my-2 border border-blue-200 dark:border-blue-800 rounded-lg bg-blue-50 dark:bg-blue-900/20 p-3">
      <div className="text-xs font-semibold text-blue-700 dark:text-blue-300 mb-2">
        Proposed Changes
      </div>

      {diff.added_nodes.length > 0 && (
        <div className="mb-2">
          <div className="text-xs font-medium text-green-700 dark:text-green-400 mb-1">
            + Add {diff.added_nodes.length} node(s)
          </div>
          {diff.added_nodes.map((node) => (
            <div
              key={node.id}
              className="text-xs text-gray-700 dark:text-gray-300 ml-3 flex items-center gap-1"
            >
              <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
              <span className="font-medium">{node.label || node.block_implementation}</span>
              <span className="text-gray-400">({node.block_type}/{node.block_implementation})</span>
            </div>
          ))}
        </div>
      )}

      {diff.removed_nodes.length > 0 && (
        <div className="mb-2">
          <div className="text-xs font-medium text-red-700 dark:text-red-400 mb-1">
            - Remove {diff.removed_nodes.length} node(s)
          </div>
          {diff.removed_nodes.map((node) => (
            <div
              key={node.id}
              className="text-xs text-gray-700 dark:text-gray-300 ml-3 flex items-center gap-1"
            >
              <span className="inline-block w-2 h-2 rounded-full bg-red-500" />
              <span className="font-medium">{node.label || node.block_implementation}</span>
              <span className="text-gray-400">({node.block_type})</span>
            </div>
          ))}
        </div>
      )}

      {diff.added_edges.length > 0 && (
        <div className="mb-2">
          <div className="text-xs font-medium text-green-700 dark:text-green-400 mb-1">
            + Add {diff.added_edges.length} edge(s)
          </div>
          {diff.added_edges.map((edge) => (
            <div
              key={edge.id}
              className="text-xs text-gray-700 dark:text-gray-300 ml-3"
            >
              <span className="font-mono">{edge.source.slice(0, 8)}...</span>
              <span className="text-gray-400"> --[{edge.data_type}]--&gt; </span>
              <span className="font-mono">{edge.target.slice(0, 8)}...</span>
            </div>
          ))}
        </div>
      )}

      {diff.removed_edges.length > 0 && (
        <div className="mb-2">
          <div className="text-xs font-medium text-red-700 dark:text-red-400 mb-1">
            - Remove {diff.removed_edges.length} edge(s)
          </div>
          {diff.removed_edges.map((edge) => (
            <div
              key={edge.id}
              className="text-xs text-gray-700 dark:text-gray-300 ml-3"
            >
              <span className="font-mono">{edge.source.slice(0, 8)}...</span>
              <span className="text-gray-400"> --[{edge.data_type}]--&gt; </span>
              <span className="font-mono">{edge.target.slice(0, 8)}...</span>
            </div>
          ))}
        </div>
      )}

      {diff.added_nodes.length === 0 &&
        diff.removed_nodes.length === 0 &&
        diff.added_edges.length === 0 &&
        diff.removed_edges.length === 0 && (
          <div className="text-xs text-gray-500">No changes detected.</div>
        )}
    </div>
  )
}

function CopilotConfirmBar() {
  const copilotResponse = useChatStore((s) => s.copilotResponse)
  const isConfirmingApply = useChatStore((s) => s.isConfirmingApply)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const confirmCopilotChanges = useChatStore((s) => s.confirmCopilotChanges)
  const rejectCopilotChanges = useChatStore((s) => s.rejectCopilotChanges)

  if (!copilotResponse || !isConfirmingApply) return null

  return (
    <div className="border-t border-gray-200 dark:border-gray-700">
      <CopilotDiffPreview diff={copilotResponse.pipeline_diff} />
      <div className="flex gap-2 px-4 pb-3">
        <button
          onClick={rejectCopilotChanges}
          disabled={isStreaming}
          className="flex-1 px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50"
        >
          Reject
        </button>
        <button
          onClick={confirmCopilotChanges}
          disabled={isStreaming}
          className="flex-1 px-3 py-2 text-sm rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
        >
          Apply Changes
        </button>
      </div>
    </div>
  )
}

function MessageInput({ pipelineId }: { pipelineId?: string }) {
  const mode = useChatStore((s) => s.mode)
  const sendMessage = useChatStore((s) => s.sendMessage)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const isConfirmingApply = useChatStore((s) => s.isConfirmingApply)
  const inputRef = useRef<HTMLInputElement>(null)

  const placeholder =
    mode === 'copilot'
      ? 'Describe how to modify the pipeline...'
      : 'Ask about research methodology...'

  const handleSubmit = () => {
    const value = inputRef.current?.value.trim()
    if (value && !isStreaming && !isConfirmingApply) {
      sendMessage(value, pipelineId)
      if (inputRef.current) {
        inputRef.current.value = ''
      }
    }
  }

  return (
    <div className="flex gap-2 p-4 border-t border-gray-200 dark:border-gray-700">
      <input
        ref={inputRef}
        type="text"
        placeholder={placeholder}
        className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 dark:bg-gray-700 dark:text-gray-100"
        disabled={isStreaming || isConfirmingApply}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            handleSubmit()
          }
        }}
      />
      <button
        onClick={handleSubmit}
        disabled={isStreaming || isConfirmingApply}
        className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 flex-shrink-0"
      >
        Send
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main ChatPanel component
// ---------------------------------------------------------------------------

interface ChatPanelProps {
  pipelineId?: string
}

export function ChatPanel({ pipelineId }: ChatPanelProps) {
  const closeChat = useChatStore((s) => s.closeChat)

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 w-96">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Research Assistant
        </h2>
        <button
          onClick={closeChat}
          className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 p-1"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            viewBox="0 0 24 24"
          >
            <path d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Mode Selector */}
      <ModeSelector />

      {/* Messages */}
      <MessageList />

      {/* Co-pilot confirm/reject bar */}
      <CopilotConfirmBar />

      {/* Input */}
      <MessageInput pipelineId={pipelineId} />
    </div>
  )
}
