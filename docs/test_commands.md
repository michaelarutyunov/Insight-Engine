# Test & Run Commands

## Phase 1 — Graph Editor with Backend

Each command runs in its own terminal.

**Terminal 1 — Backend API**
```bash
cd backend && uv run uvicorn main:app --reload
# Available at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

**Terminal 2 — Frontend canvas**
```bash
cd frontend && npm run dev
# Available at http://localhost:5173
# Connects to backend on :8000
```

**Terminal 3 — Automated tests**
```bash
cd backend && uv run pytest
```

**What you can test:** drag blocks from the palette onto the canvas, draw typed edges, save and load pipelines. Pipeline *execution* is Phase 2.
