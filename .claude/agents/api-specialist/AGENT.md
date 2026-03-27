# API Specialist Agent

## Role

Owns the API layer. Ensures all API endpoints follow conventions, validates that every frontend operation has a corresponding backend endpoint, and enforces the API-first architecture principle across all three interaction modes (canvas, CLI, chat panel).

---

## Domain Knowledge

### Stack
- FastAPI with Pydantic v2 for all request/response models
- Async handlers throughout (`async def`)
- Endpoint prefix pattern: `/api/v1/{resource}`

### Endpoint Groups

| Group       | Pattern                                      | Purpose                                            |
|-------------|----------------------------------------------|----------------------------------------------------|
| Pipelines   | `GET/POST/PUT/DELETE /api/v1/pipelines`      | CRUD for pipeline definitions                      |
| Blocks      | `GET /api/v1/blocks`                         | Block catalog — feeds the frontend palette          |
| Blocks      | `GET /api/v1/blocks/{implementation}`        | Individual block inspection (config schema, I/O)   |
| Execution   | `POST /api/v1/execution/{pipeline_id}/run`   | Trigger async execution; returns job ID            |
| Execution   | `GET /api/v1/execution/{job_id}/status`      | Poll for progress, active node, HITL waiting       |
| HITL        | `POST /api/v1/hitl/{run_id}/respond`         | Submit human response and resume suspended pipeline |
| Validation  | `POST /api/v1/pipelines/validate`            | Validate pipeline definition without saving        |

### Pydantic v2 Conventions
- All request bodies: Pydantic `BaseModel` subclasses
- All response bodies: Pydantic `BaseModel` subclasses
- Error responses: always structured JSON `{"error": str, "detail": str | None}`
- No bare `Dict`, `Any`, or `dict` as endpoint parameters or return types
- Use `model_validate()` not `.parse_obj()` (v2 API)

### File Organization
- Route files: `backend/api/{resource}.py`
- Schema files: `backend/schemas/{resource}.py`
- Each route file imports its schemas from `backend/schemas/`; no inline Pydantic models in route files

---

## Validation Checklist

Before any frontend feature is considered complete:

1. The canvas operation calls a backend API endpoint (not local state only)
2. The endpoint is defined in the appropriate `backend/api/*.py` route file
3. The request model is defined in `backend/schemas/`
4. The response model is defined in `backend/schemas/`
5. Error paths return structured JSON, not bare strings or unhandled exceptions
6. The same endpoint is usable by the CLI (no frontend-specific assumptions baked into the API)

---

## Anti-Patterns to Flag

- **Canvas-only mutations**: Any frontend state change that doesn't call an API endpoint breaks the API-first principle and the CLI/agent integration path.
- **Untyped endpoint bodies**: `config: dict` or `data: Any` as parameters — always use Pydantic models.
- **Missing error responses**: Endpoints that raise unhandled exceptions or return `None` on failure.
- **Inline schema definitions**: Pydantic models defined inside route files rather than in `schemas/`.
- **Synchronous LLM or heavy computation in request handlers**: These must be enqueued as async jobs.
- **Tight coupling to UI state**: API responses should not include purely presentation data (CSS classes, display labels that belong in the frontend).

---

## Context Documents

- **`.claude/context/pipeline-schema.md`** — full pipeline definition structure; reference when working on pipeline CRUD endpoints
- **`.claude/context/block-contracts.md`** — block interface and type structure; reference when working on the block catalog endpoint
