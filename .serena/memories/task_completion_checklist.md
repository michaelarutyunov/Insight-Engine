# Task Completion Checklist

Run these before marking any task done:

1. `ruff check . --fix` — auto-fix linting issues
2. `ruff format .` — format code
3. LSP diagnostics — resolve all errors (pyright via LSP tool)
4. `uv run pytest` — all tests pass
5. Update relevant bead: `bd update <id>`, `bd close <id>`, `bd sync`
6. Create ADR in `docs/adr/` if an architectural decision was made
7. Update `CLAUDE.md` context docs if data flows or APIs changed

## Session close protocol
```bash
git status
git add <files>
bd sync
git commit -m "..."
bd sync
git push
```
