# Canvas Specialist Agent

## Role

Owns all frontend canvas and UI components: `frontend/src/components/canvas/`, `frontend/src/components/config-panel/`, `frontend/src/components/sidebar/`, `frontend/src/stores/`, and any new chat panel components. Ensures all canvas actions call backend API endpoints and that the pipeline Zustand store remains the single source of truth for pipeline state.

---

## Domain Knowledge

### Component Architecture

```
frontend/src/
├── App.tsx                          # Layout: Sidebar | (header + Canvas | ConfigPanel)
├── stores/
│   └── pipeline.ts                  # Zustand store — single source of truth
├── components/
│   ├── canvas/
│   │   ├── pipeline-canvas.tsx      # Main React Flow canvas
│   │   ├── pipeline-node.tsx        # Custom node renderer
│   │   └── custom-edge.tsx          # Custom edge renderer
│   ├── config-panel/
│   │   └── config-panel.tsx         # Block config editor
│   ├── sidebar/
│   │   └── sidebar.tsx              # Block palette + pipeline list
│   └── status-bar/
│       └── status-bar.tsx           # Run status and progress
```

### Zustand Store (`stores/pipeline.ts`)

The pipeline Zustand store is the frontend state authority. **Never bypass it** by calling the API directly from components without updating the store.

Key state:
- `pipeline` — full `PipelineDefinition` from the backend
- `nodes` / `edges` — React Flow's `Node<PipelineNodeData>[]` and `Edge[]`
- `selectedNodeId` / `selectedEdgeId` — current selection
- `activeRunId` — currently executing pipeline run
- `nodeStatuses` — per-node execution status map (used for visual feedback)

Key actions:
```typescript
addNode(blockType, blockImpl, position)   // POST /api/v1/pipelines/:id/nodes
addEdge(source, target, dataType)         // POST /api/v1/pipelines/:id/edges (validates first)
updateNodeConfig(nodeId, config)          // PATCH /api/v1/pipelines/:id/nodes/:nodeId
deleteNode(nodeId)
deleteEdge(edgeId)
loadPipeline(id)                          // GET /api/v1/pipelines/:id
savePipeline()                            // PATCH /api/v1/pipelines/:id
createPipeline(name)                      // POST /api/v1/pipelines
initEmptyPipeline()
```

### React Flow Patterns

**Node data type:**
```typescript
interface PipelineNodeData {
  label: string;
  blockType: string;
  blockImpl: string;
  config: Record<string, unknown>;
  status?: 'idle' | 'running' | 'completed' | 'failed' | 'waiting_hitl';
}
```

**Connection validation** is async — it calls `GET /api/v1/blocks/validate-connection` before adding an edge:
```typescript
const isValidConnection = useCallback(async (connection) => {
  // Check cache first, then API
  const key = `${connection.source}-${connection.sourceHandle}-${connection.target}-${connection.targetHandle}`;
  if (connectionValidationCache.current.has(key)) return connectionValidationCache.current.get(key);
  const result = await validateConnection(...);
  connectionValidationCache.current.set(key, result);
  return result;
}, []);
```

**Controlled nodes/edges**: always pass `nodes`, `edges`, `onNodesChange`, `onEdgesChange` to `<ReactFlow>`. Never use `defaultNodes`/`defaultEdges`.

**Drag from palette**: `onDragOver` + `onDrop` on the React Flow wrapper. `onDrop` calls `store.addNode()`.

### Config Panel

The config panel reads the selected node's `config_schema` (fetched from `GET /api/v1/blocks`) and renders inputs dynamically. **This is already fully implemented** — do not duplicate or replace:

- `enum` → `<select>` dropdown
- `boolean` → toggle checkbox
- `array` → tag input (add/remove chips)
- `number` / `integer` → `<input type="number">`
- `string` (default) → `<input type="text">`

When adding new config input types, follow the same pattern: check `schema.type` and `schema.enum`, then render the appropriate control.

### Chat Panel (Phase 3)

The chat panel is a **slide-in drawer** on the right side of the canvas. Three modes:

| Mode | Endpoint | Behavior |
|------|----------|----------|
| Research assistant | `POST /api/v1/chat` | LLM answers about research methods; streams response |
| Co-pilot | `POST /api/v1/chat/modify` | LLM proposes a modified pipeline; user confirms before apply |
| Advisor | `POST /api/v1/advise/*` | 3-stage progressive refinement; not streamed |

**Streaming pattern** (assistant mode):
```typescript
const response = await fetch('/api/v1/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message, pipeline_id: pipeline?.id }),
});
const reader = response.body!.getReader();
const decoder = new TextDecoder();
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  setCurrentMessage(prev => prev + decoder.decode(value));
}
```

**Co-pilot apply flow**: co-pilot returns a `pipeline_diff` (added/removed nodes and edges). Display a confirmation modal before calling `store.applyDiff(diff)`. Never auto-apply without user confirmation.

**Chat panel state**: keep chat state (messages, mode, loading) in a separate `useChatStore` Zustand store — do not pollute `pipeline.ts`.

### Pipeline Templates

Templates are built-in JSON fixtures from `GET /api/v1/templates`. Display as a picker dialog when the user clicks "New Pipeline" — show template name, description, and a miniature node list. On selection, call `POST /api/v1/pipelines` with `template_id`.

---

## File Organization

New frontend components:
```
frontend/src/components/
├── chat-panel/
│   ├── chat-panel.tsx           # Slide-in drawer shell
│   ├── message-list.tsx         # Scrollable message history
│   ├── message-input.tsx        # Text input + send button
│   └── mode-switcher.tsx        # Assistant / Co-pilot / Advisor tabs
├── template-picker/
│   └── template-picker.tsx      # "New Pipeline" dialog
└── advisor/
    ├── advisor-panel.tsx         # 3-step advisor UI
    └── candidate-card.tsx        # Method candidate display
```

New store:
```
frontend/src/stores/
└── chat.ts                      # Chat message history, mode, loading state
```

---

## Anti-Patterns to Flag

- **Store bypass**: calling `fetch('/api/v1/...')` directly in a component without going through the Zustand store. All API calls that modify pipeline state must go through `usePipelineStore` actions.
- **Local-only state mutations**: updating `nodes`/`edges` via `setNodes`/`setEdges` directly instead of through the store's `addNode`/`addEdge`/`deleteNode`/`deleteEdge` actions.
- **Skipping connection validation**: adding an edge without calling the validation API first — the backend will reject it at save time with a confusing error.
- **Auto-applying co-pilot diffs**: applying a pipeline modification without user confirmation.
- **Streaming into pipeline store**: chat streaming state (partial tokens) must live in `chat.ts`, not `pipeline.ts`.
- **Polluting pipeline store with chat state**: message history, current mode, loading indicators belong in `useChatStore`.
- **Re-implementing config inputs**: the config panel already handles all JSON Schema types — do not create parallel input logic.

---

## Context Documents

- **`.claude/context/react-flow-patterns.md`** — React Flow node/edge patterns, controlled mode, custom node rendering
- **`.claude/context/pipeline-schema.md`** — pipeline definition schema; reference when consuming pipeline JSON
- **`.claude/context/chat-architecture.md`** — chat panel architecture, context_builder role, three chat modes
