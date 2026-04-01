/**
 * Chat store — Zustand store for the chat panel.
 *
 * Manages message history, streaming state, and the API interaction
 * for the research assistant chat mode.  Chat state lives here,
 * NOT in the pipeline store.
 */
import { create } from 'zustand'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export type ChatMode = 'assistant' | 'copilot' | 'advisor'

export interface NodeDiff {
  id: string
  block_type: string
  block_implementation: string
  label: string
  config: Record<string, unknown>
  position: [number, number]
  input_schema: string[]
  output_schema: string[]
}

export interface EdgeDiff {
  id: string
  source: string
  target: string
  data_type: string
}

export interface PipelineDiff {
  added_nodes: NodeDiff[]
  removed_nodes: NodeDiff[]
  added_edges: EdgeDiff[]
  removed_edges: EdgeDiff[]
}

export interface CopilotResponse {
  explanation: string
  pipeline_diff: PipelineDiff
}

interface ChatStore {
  // --- state ---
  messages: ChatMessage[]
  mode: ChatMode
  isOpen: boolean
  isStreaming: boolean
  currentStreamingContent: string
  error: string | null
  copilotResponse: CopilotResponse | null
  isConfirmingApply: boolean

  // --- actions ---
  openChat: () => void
  closeChat: () => void
  toggleChat: () => void
  setMode: (mode: ChatMode) => void
  sendMessage: (message: string, pipelineId?: string) => Promise<void>
  clearMessages: () => void
  confirmCopilotChanges: () => Promise<void>
  rejectCopilotChanges: () => void
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/**
 * Send a chat message and consume the SSE stream.
 * Returns the full streamed response text.
 */
async function streamChatMessage(
  message: string,
  pipelineId?: string,
  onChunk: (chunk: string) => void,
): Promise<void> {
  const body: Record<string, string> = { message }
  if (pipelineId) {
    body.pipeline_id = pipelineId
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new Error(`Chat API error: ${response.status}`)
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()

  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // SSE: split on newlines and parse each JSON line
    const lines = buffer.split('\n')
    // Keep the last incomplete line in the buffer
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue

      try {
        const chunk = JSON.parse(trimmed)
        if (chunk.type === 'token') {
          onChunk(chunk.content)
        } else if (chunk.type === 'error') {
          throw new Error(chunk.content)
        }
        // 'done' — stream complete
      } catch (e) {
        if (e instanceof SyntaxError) {
          // Skip malformed JSON lines
          continue
        }
        throw e
      }
    }
  }
}

/**
 * Send a co-pilot modification request and return the structured diff.
 */
async function fetchCopilotModification(
  message: string,
  pipelineId: string,
): Promise<CopilotResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/chat/modify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, pipeline_id: pipelineId }),
  })

  if (!response.ok) {
    const errorBody = await response.text()
    throw new Error(`Co-pilot API error: ${response.status} — ${errorBody}`)
  }

  return response.json()
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

let messageIdCounter = 0
function nextId(): string {
  messageIdCounter += 1
  return `msg-${messageIdCounter}`
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  mode: 'assistant',
  isOpen: false,
  isStreaming: false,
  currentStreamingContent: '',
  error: null,
  copilotResponse: null,
  isConfirmingApply: false,

  openChat: () => set({ isOpen: true }),
  closeChat: () => set({ isOpen: false }),

  toggleChat: () => set((state) => ({ isOpen: !state.isOpen })),

  setMode: (mode) => set({ mode, messages: [], error: null, copilotResponse: null }),

  sendMessage: async (message, pipelineId) => {
    const { mode } = get()

    const userMessage: ChatMessage = {
      id: nextId(),
      role: 'user',
      content: message,
      timestamp: Date.now(),
    }

    set((state) => ({
      messages: [...state.messages, userMessage],
      isStreaming: true,
      currentStreamingContent: '',
      error: null,
      copilotResponse: null,
    }))

    if (mode === 'copilot' && pipelineId) {
      // Co-pilot mode: call the modify endpoint and get a structured diff
      try {
        const copilotResponse = await fetchCopilotModification(message, pipelineId)

        const assistantMessage: ChatMessage = {
          id: nextId(),
          role: 'assistant',
          content: copilotResponse.explanation,
          timestamp: Date.now(),
        }

        set((state) => ({
          messages: [...state.messages, assistantMessage],
          isStreaming: false,
          copilotResponse,
          isConfirmingApply: true,
        }))
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Co-pilot error'
        const assistantMessage: ChatMessage = {
          id: nextId(),
          role: 'assistant',
          content: `Error: ${errorMsg}`,
          timestamp: Date.now(),
        }
        set((state) => ({
          messages: [...state.messages, assistantMessage],
          isStreaming: false,
          error: errorMsg,
        }))
      }
      return
    }

    // Assistant mode: stream the response
    const assistantMessageId = nextId()
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    }

    set((state) => ({
      messages: [...state.messages, assistantMessage],
    }))

    try {
      await streamChatMessage(message, pipelineId, (chunk) => {
        set((state) => {
          const updatedMessages = state.messages.map((m) =>
            m.id === assistantMessageId
              ? { ...m, content: m.content + chunk }
              : m,
          )
          return {
            messages: updatedMessages,
            currentStreamingContent: state.currentStreamingContent + chunk,
          }
        })
      })
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Chat error'

      // Update the assistant message with the error
      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === assistantMessageId
            ? { ...m, content: m.content || `Error: ${errorMsg}` }
            : m,
        ),
        error: errorMsg,
      }))
    } finally {
      set({ isStreaming: false, currentStreamingContent: '' })
    }
  },

  clearMessages: () => set({ messages: [], error: null, copilotResponse: null }),

  confirmCopilotChanges: async () => {
    const { copilotResponse } = get()
    if (!copilotResponse) return

    set({ isConfirmingApply: false, isStreaming: true })

    try {
      // Import the pipeline store lazily to avoid circular deps
      const { usePipelineStore } = await import('./pipeline')
      const pipelineStore = usePipelineStore.getState()

      await pipelineStore.applyDiff(copilotResponse.pipeline_diff)
      await pipelineStore.savePipeline()

      set({ copilotResponse: null, isStreaming: false })
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to apply changes'
      set({
        error: errorMsg,
        isStreaming: false,
      })
    }
  },

  rejectCopilotChanges: () => {
    set({ copilotResponse: null, isConfirmingApply: false })
  },
}))
