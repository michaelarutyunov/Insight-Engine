# Suggested Commands

## Backend
```bash
cd backend && uvicorn main:app --reload    # Run dev server
uv run pytest                             # Run tests
ruff check backend/                       # Lint
ruff format backend/                      # Format
uv add <package>                          # Add dependency
uv add --dev <package>                    # Add dev dependency
```

## Frontend
```bash
cd frontend && npm run dev                # Run dev server
npm run build                             # Build
npm run lint                              # Lint
```

## Project tooling
```bash
bd ready                                  # Show ready beads/tasks
bd create --title="..." --type=task       # Create issue
bd update <id> --status=in_progress       # Claim task
bd close <id>                             # Mark complete
bd sync                                   # Commit beads state
git status / git diff / git log           # Git inspection
ruff check . --fix && ruff format .       # Fix + format all
python3 .claude/scripts/context-drift-check.py  # Validate knowledge layer
```

## Never use
- `pip` — always use `uv`
- `find` — use `fd`
- `grep` — use `rg`
