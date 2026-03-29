---
name: smoke-test
description: Use when verifying the Insight-Engine stack is working after a phase completes, after a session interruption, or before starting a new phase. Triggered by /smoke-test or "is everything working", "quick sanity check", "test the stack".
---

# smoke-test — Insight-Engine Stack Verification

## What This Checks

1. Backend starts and responds
2. Key API endpoints return valid responses
3. Block registry is populated
4. A minimal pipeline can be created and validated
5. Frontend builds (if requested)
6. Automated tests pass

## Process

### Step 1 — Run automated tests
```bash
cd backend && uv run pytest -q
```
If any tests fail: stop and report. Do not proceed.

### Step 2 — Start backend (background)
```bash
cd backend && uv run uvicorn main:app --port 8000 &
sleep 2
```

### Step 3 — Hit key endpoints
```bash
# Health
curl -s http://localhost:8000/health | python3 -m json.tool

# Block catalog — must return non-empty list
curl -s http://localhost:8000/api/v1/blocks | python3 -c "
import sys, json
blocks = json.load(sys.stdin)
print(f'Blocks registered: {len(blocks)}')
assert len(blocks) > 0, 'Block catalog is empty'
print('OK')
"

# Pipeline CRUD — create, read, delete (one pipeline, cleaned up)
PIPELINE_ID=$(curl -s -X POST http://localhost:8000/api/v1/pipelines \
  -H 'Content-Type: application/json' \
  -d '{"name":"smoke-test","description":"","nodes":[],"edges":[]}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Pipeline created: $PIPELINE_ID"

curl -s http://localhost:8000/api/v1/pipelines/$PIPELINE_ID \
  | python3 -c "import sys,json; p=json.load(sys.stdin); assert 'id' in p; print('Pipeline GET OK')"

curl -s -X DELETE http://localhost:8000/api/v1/pipelines/$PIPELINE_ID
echo "Pipeline DELETE OK"
```

### Step 4 — Check Phase 2 execution endpoint (if applicable)
```bash
# Verify execution route exists
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/execution/nonexistent/run
# Expect 404 (route exists, pipeline doesn't) not 405 (route missing)
```

### Step 5 — Stop background server
```bash
kill %1 2>/dev/null || pkill -f "uvicorn main:app" 2>/dev/null
```

### Step 6 — Report

Print a summary:
```
SMOKE TEST RESULTS
==================
✓ Automated tests: N passed
✓ Backend: started on :8000
✓ Block catalog: N blocks registered
✓ Pipeline CRUD: create/read/delete OK
✓ Execution route: present
==================
Stack is healthy.
```

Or if anything failed:
```
✗ [step name]: [what failed]
Stack is NOT healthy — do not proceed with implementation.
```

## When to Skip Steps

- Step 4 (execution endpoint): skip if only Phase 1 is implemented
- Step 6 frontend build: only run if frontend changes were made in this session (`cd frontend && npm run build`)
- Steps 2–5: skip if running in CI or if only running automated tests is sufficient

## Notes

- The background server (`&`) may conflict if port 8000 is already in use. Check with `lsof -i :8000` first.
- `sleep 2` is needed for uvicorn to finish starting. Increase to 3 if on a slow machine.
- This skill does not test end-to-end pipeline execution (that requires ANTHROPIC_API_KEY and real data).
