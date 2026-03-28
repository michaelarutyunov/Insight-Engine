import Sidebar from './components/Sidebar'
import { PipelineCanvas } from './components/canvas'
import { ConfigPanel } from './components/config-panel'
import { SaveLoadToolbar } from './components/toolbar'

function App() {
  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Insight Engine
          </h1>
          <SaveLoadToolbar />
        </header>
        <div className="flex flex-1 min-h-0">
          <div className="flex-1">
            <PipelineCanvas />
          </div>
          <ConfigPanel />
        </div>
      </div>
    </div>
  )
}

export default App
