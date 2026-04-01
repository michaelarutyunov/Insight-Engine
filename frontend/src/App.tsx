import Sidebar from './components/Sidebar'
import { PipelineCanvas } from './components/canvas'
import { ConfigPanel } from './components/config-panel'
import { ChatPanel } from './components/chat-panel'
import { SaveLoadToolbar } from './components/toolbar'
import { usePipelineStore } from './stores/pipeline'
import { useChatStore } from './stores/chat'

function App() {
  const pipeline = usePipelineStore((s) => s.pipeline)
  const isChatOpen = useChatStore((s) => s.isOpen)
  const toggleChat = useChatStore((s) => s.toggleChat)

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Insight Engine
          </h1>
          <div className="flex items-center gap-2">
            <SaveLoadToolbar />
            <button
              onClick={toggleChat}
              className="relative p-2 text-gray-400 hover:text-gray-600 transition-colors"
              title={isChatOpen ? 'Close chat' : 'Open chat'}
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </button>
          </div>
        </header>
        <div className="flex flex-1 min-h-0">
          <div className="flex-1">
            <PipelineCanvas />
          </div>
          {isChatOpen && (
            <div className="w-96 border-l border-gray-200 dark:border-gray-700">
              <ChatPanel pipelineId={pipeline?.id || undefined} />
            </div>
          )}
        </div>
      </div>
      <ConfigPanel />
    </div>
  )
}

export default App
