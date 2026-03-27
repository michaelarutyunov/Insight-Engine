# Insights IDE — Project Overview

## Purpose
Visual pipeline IDE for insights professionals. Research workflows as node-and-edge graphs where the pipeline itself is the artifact. Lets researchers build, save, version, share, and reuse research designs.

## Current Phase
Phase 1 — graph editor with backend skeleton. No backend or frontend code exists yet.

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLite (→ PostgreSQL in Phase 3+)
- **Frontend**: React, TypeScript (strict), React Flow
- **LLM**: Anthropic API (Claude) for Generation, Evaluation, LLM Flex blocks
- **Cloud**: Google Cloud (Cloud Run, Cloud Storage, Cloud Tasks)
- **Package manager**: uv (never pip)

## Architecture Principles
- API-FIRST: every frontend operation has a backend endpoint; no canvas-only functionality
- BLOCK CONTRACTS: all blocks implement BlockBase; type and implementation are separate
- TYPED EDGES: edge data_type must match source output_schema and target input_schema
- PIPELINE JSON IS THE ARTIFACT: pipeline definition schema is the core data structure

## Interaction Modes
Three modes, all consuming the same API:
1. Visual canvas (React Flow)
2. CLI (Python/Typer, Phase 2+)
3. Chat panel (Phase 3+)
