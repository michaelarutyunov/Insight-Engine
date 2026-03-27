# Code Style & Conventions

## Python
- Python 3.11+, type hints everywhere
- Pydantic v2 for all schemas (use `model_validate()` not `.parse_obj()`)
- `snake_case` for files, variables, functions
- One file per block implementation: `blocks/{type}/{implementation}.py`
- All block base classes in `blocks/base.py`; blocks must not import from sibling blocks
- `async def execute(...)` — all block execute methods are async
- No bare `Dict`, `Any`, `dict` as endpoint params/returns; always Pydantic models
- Linter: ruff; type checker: pyright (via LSP)

## TypeScript/Frontend
- Strict mode
- `kebab-case` for component files
- All canvas actions must call API endpoints — no local-only state mutations

## File naming
- Python: `snake_case`
- Frontend components: `kebab-case`

## API routes
- Pattern: `/api/v1/{resource}`
- Route files: `backend/api/{resource}.py`
- Schema files: `backend/schemas/{resource}.py` (no inline Pydantic models in route files)

## Testing
- pytest for all backend tests
- Every block must have `test_fixtures()` method
- Deterministic blocks: fixed input → exact output
- LLM blocks: mock API call, test prompt + response parsing
- Run `uv run pytest` before marking any task complete

## Commits
- Conventional commits: feat:, fix:, docs:, refactor:, test:
- Co-authored-by: Claude Code
- Run ruff before committing
