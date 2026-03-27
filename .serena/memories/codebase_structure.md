# Codebase Structure (planned — Phase 1 not yet built)

```
Insight-Engine/
├── CLAUDE.md                        # Agent constitution (always loaded)
├── AGENTS.md
├── backend/
│   ├── main.py                      # FastAPI entry point
│   ├── api/
│   │   ├── pipelines.py             # Pipeline CRUD
│   │   ├── execution.py             # Run trigger + status polling
│   │   ├── blocks.py                # Block catalog
│   │   └── hitl.py                  # HITL response + resume
│   ├── engine/
│   │   ├── executor.py              # Graph walker
│   │   ├── validator.py             # Edge type checking
│   │   ├── state.py                 # HITL state persistence
│   │   ├── registry.py              # Block discovery
│   │   └── loop_controller.py       # Loop termination
│   ├── blocks/
│   │   ├── base.py                  # All base classes
│   │   ├── sources/
│   │   ├── transforms/
│   │   ├── generation/
│   │   ├── evaluation/
│   │   ├── comparison/
│   │   ├── reporting/
│   │   ├── llm_flex/
│   │   ├── routing/
│   │   ├── hitl/
│   │   └── sinks/
│   ├── schemas/
│   │   ├── pipeline.py              # Pipeline Pydantic models
│   │   ├── block_types.py           # Block type enums
│   │   └── data_objects.py          # Research data schemas
│   ├── db/
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/canvas/
│       └── stores/pipeline.ts       # Zustand pipeline state
├── .claude/
│   ├── agents/
│   │   ├── api-specialist/AGENT.md
│   │   └── block-developer/AGENT.md
│   ├── context/
│   │   ├── pipeline-schema.md
│   │   └── block-contracts.md
│   └── scripts/
│       └── context-drift-check.py
└── docs/
    ├── adr/                         # Architecture Decision Records
    └── initiation/                  # Vision + blueprint docs
```

## Key files (once built)
- `backend/blocks/base.py` — BlockBase and all type-specific bases
- `backend/engine/executor.py` — core execution loop
- `backend/schemas/pipeline.py` — pipeline definition Pydantic models
- `backend/schemas/data_objects.py` — research data object schemas
- `frontend/src/stores/pipeline.ts` — frontend state
