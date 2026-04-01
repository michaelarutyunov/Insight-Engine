# Deep Code Quality — Insights IDE Project Adaptations

## Project-Specific Configuration

This skill extends the generic deep-code-quality skill with Insights IDE conventions.

## What's Different Here

### Code Quality Standards
- **Ruff**: Primary linter/formatter (not flake8/black mix)
- **Pyright**: Type checker (not mypy)
- **pytest**: Test framework (not unittest)
- **Pydantic v2**: All schemas use Pydantic v2, not v1

### File Organization Patterns
- Blocks: One file per implementation in `blocks/{type}/{name}.py`
- Tests: Mirror structure `tests/blocks/test_{name}.py`
- No `__init__.py` in test directories (pytest auto-discovers)
- Frontend components: `kebab-case` naming in `frontend/src/components/`

### LSP Integration Pattern
**CRITICAL**: Before closing any bead or committing code:
```bash
# For all modified .py files
LSP(operation: "getDiagnostics", filePath: "path/to/file.py")
```
This catches syntax/type errors before runtime. See CLAUDE.md "Code Quality Workflow".

### Contract Testing Requirements
- All blocks must pass generic contract tests in `tests/blocks/test_contract.py`
- LLM blocks: Mock the API, test prompt construction
- Deterministic blocks: Fixed input → assert exact output
- Every block must include `test_fixtures()` with sample data

### Dimensional Requirements for Analysis Blocks
Analysis blocks must have a `dimensions` property returning 6-dimension dict:
```python
@property
def dimensions(self) -> dict[str, str]:
    return {
        "exploratory_confirmatory": "confirmatory",
        "assumption_weight": "medium",
        "output_interpretability": "high",
        "sample_sensitivity": "medium",
        "reproducibility": "high",
        "data_structure_affinity": "numeric_continuous",
    }
```
Validate against `backend/reasoning/dimensions.py` allowed sets.

### Integration with Codified Context
When invoked, this skill automatically loads:
- `.claude/context/block-contracts.md` (before reviewing blocks)
- `CLAUDE.md` (project conventions)
- `.claude/agents/block-developer/AGENT.md` (block patterns)

### Backend vs Frontend Split
- Backend runs from `/backend` directory
- Frontend runs from `/` (root) with `/frontend` subdirectory
- Tests always run from backend: `cd backend && uv run pytest`

### Common Anti-Patterns to Flag
- Blocks importing from other block implementations (violates independence)
- API endpoints returning untyped `dict` instead of Pydantic models
- Frontend state mutations that bypass the API (violates API-FIRST)
- Missing `description` or `methodological_notes` properties on blocks
- Tests that don't use `test_fixtures()` for sample data

## Exit Criteria
Code passes when:
1. ✅ LSP diagnostics show zero errors (warnings OK)
2. ✅ `ruff check . --fix` passes
3. ✅ `ruff format .` applied
4. ✅ Scoped tests pass (`pytest tests/blocks/test_<name>.py`)
5. ✅ All block contract tests pass

## Session Recovery Pattern
When resuming an interrupted session:
1. Check `bd list --status=in_progress` for partial work
2. For each in_progress bead:
   - Read the code to assess actual state
   - If complete and tested → `bd close`
   - If partial → dispatch with instruction to complete
   - If nothing written → `bd update --status=open` to reset
3. Run this skill before marking beads complete

## Testing Strategy
- **Before closing a bead**: Run scoped tests only
  - Block bead → `pytest tests/blocks/test_<implementation>.py`
  - Reasoning/chat → `pytest tests/reasoning/ tests/chat/`
  - API bead → `pytest tests/api/`
  - CLI bead → `pytest tests/cli/`
- **After closing a wave of beads**: Run full test suite once
  - `cd backend && uv run pytest`
- **Never run full suite after every single bead** (too slow)

## Co-Authorship Convention
All commits include:
```
Co-Authored-By: Claude Code (Sonnet/Opus/Haiku) <noreply@anthropic.com>
```
Use appropriate model name based on which model was used.
