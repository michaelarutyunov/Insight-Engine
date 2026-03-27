#!/usr/bin/env python3
"""
Context drift check for Insights IDE.

Validates cross-references between the constitution (CLAUDE.md),
agent specs (.claude/agents/*/AGENT.md), and context docs
(.claude/context/*.md). Run at session start or as a pre-commit hook.

Usage:
    python .claude/scripts/context-drift-check.py
    python .claude/scripts/context-drift-check.py --strict   # exit 1 on warnings

Exit codes:
    0 — all checks passed (warnings may exist without --strict)
    1 — one or more errors or (with --strict) warnings
"""

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config — paths relative to repo root
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent
CONSTITUTION = REPO_ROOT / "CLAUDE.md"
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
CONTEXT_DIR = REPO_ROOT / ".claude" / "context"

# Key files declared in the constitution's Key File Map.
# Update this list when CLAUDE.md's Key Files section changes.
KEY_FILES = [
    "backend/blocks/base.py",
    "backend/engine/executor.py",
    "backend/engine/validator.py",
    "backend/engine/state.py",
    "backend/engine/registry.py",
    "backend/engine/loop_controller.py",
    "backend/schemas/pipeline.py",
    "backend/schemas/data_objects.py",
    "backend/api/pipelines.py",
    "backend/api/execution.py",
    "backend/api/blocks.py",
    "backend/api/hitl.py",
    "frontend/src/stores/pipeline.ts",
]

# Agent names declared in the Agent Trigger Table.
# Update when CLAUDE.md's trigger table changes.
TRIGGER_TABLE_AGENTS = [
    "engine-specialist",
    "block-developer",
    "canvas-specialist",
    "api-specialist",
    "schema-specialist",
    "llm-integration",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

errors: list[str] = []
warnings: list[str] = []


def error(msg: str) -> None:
    errors.append(f"  ERROR   {msg}")


def warn(msg: str) -> None:
    warnings.append(f"  WARN    {msg}")


def ok(msg: str) -> None:
    print(f"  ok      {msg}")


def section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


# ---------------------------------------------------------------------------
# Check 1: Constitution exists and is readable
# ---------------------------------------------------------------------------


def check_constitution_exists() -> None:
    section("1. Constitution")
    if not CONSTITUTION.exists():
        error(f"CLAUDE.md not found at {CONSTITUTION}")
        return
    ok(f"CLAUDE.md exists ({CONSTITUTION.stat().st_size} bytes)")

    text = CONSTITUTION.read_text()
    for marker in ["## Block Types", "## Agent Trigger Table", "## Key File Map"]:
        if marker in text:
            ok(f"Section found: '{marker}'")
        else:
            error(f"Required section missing from CLAUDE.md: '{marker}'")


# ---------------------------------------------------------------------------
# Check 2: Key files referenced in constitution actually exist
# ---------------------------------------------------------------------------


def check_key_files() -> None:
    section("2. Key File Map — file existence")
    for rel_path in KEY_FILES:
        full_path = REPO_ROOT / rel_path
        if full_path.exists():
            ok(rel_path)
        else:
            warn(f"Key file not yet created: {rel_path}")


# ---------------------------------------------------------------------------
# Check 3: Agent directories and AGENT.md files
# ---------------------------------------------------------------------------


def check_agent_specs() -> None:
    section("3. Agent specs")

    if not AGENTS_DIR.exists():
        error(f".claude/agents/ directory not found at {AGENTS_DIR}")
        return

    found_agents = [d.name for d in AGENTS_DIR.iterdir() if d.is_dir()]

    for agent_name in TRIGGER_TABLE_AGENTS:
        agent_dir = AGENTS_DIR / agent_name
        agent_md = agent_dir / "AGENT.md"
        if not agent_dir.exists():
            warn(f"Agent in trigger table has no directory: {agent_name}/")
        elif not agent_md.exists():
            error(f"Agent directory exists but AGENT.md missing: {agent_name}/AGENT.md")
        else:
            ok(f"{agent_name}/AGENT.md")

    for found in found_agents:
        if found not in TRIGGER_TABLE_AGENTS:
            warn(
                f"Agent directory exists but not in CLAUDE.md trigger table: {found}/ "
                f"— add it to the Agent Trigger Table or remove the directory"
            )


# ---------------------------------------------------------------------------
# Check 4: Context docs referenced in agent specs actually exist
# ---------------------------------------------------------------------------


def check_agent_context_references() -> None:
    section("4. Agent → context doc cross-references")

    if not AGENTS_DIR.exists():
        warn("Skipping — agents directory not found")
        return

    context_ref_pattern = re.compile(r"`\.claude/context/([\w-]+\.md)`")

    for agent_md in sorted(AGENTS_DIR.glob("*/AGENT.md")):
        agent_name = agent_md.parent.name
        text = agent_md.read_text()
        refs = context_ref_pattern.findall(text)
        for ref in refs:
            context_file = CONTEXT_DIR / ref
            if context_file.exists():
                ok(f"{agent_name} → context/{ref}")
            else:
                error(
                    f"{agent_name}/AGENT.md references missing context doc: "
                    f".claude/context/{ref}"
                )


# ---------------------------------------------------------------------------
# Check 5: Context docs referenced in constitution actually exist
# ---------------------------------------------------------------------------


def check_constitution_context_references() -> None:
    section("5. Constitution → context doc cross-references")

    if not CONSTITUTION.exists():
        warn("Skipping — CLAUDE.md not found")
        return

    text = CONSTITUTION.read_text()
    context_ref_pattern = re.compile(r"`\.claude/context/([\w-]+\.md)`")
    refs = context_ref_pattern.findall(text)

    if not refs:
        warn("No context doc references found in CLAUDE.md — check formatting")
        return

    for ref in refs:
        context_file = CONTEXT_DIR / ref
        if context_file.exists():
            ok(f"CLAUDE.md → context/{ref}")
        else:
            warn(
                f"CLAUDE.md references context doc not yet created: "
                f".claude/context/{ref}"
            )


# ---------------------------------------------------------------------------
# Check 6: Orphan context docs (exist but not referenced anywhere)
# ---------------------------------------------------------------------------


def check_orphan_context_docs() -> None:
    section("6. Orphan context docs")

    if not CONTEXT_DIR.exists():
        ok("No context directory yet — nothing to check")
        return

    all_refs: set[str] = set()

    # Gather refs from constitution
    if CONSTITUTION.exists():
        text = CONSTITUTION.read_text()
        all_refs.update(re.findall(r"`\.claude/context/([\w-]+\.md)`", text))

    # Gather refs from agent specs
    for agent_md in AGENTS_DIR.glob("*/AGENT.md"):
        text = agent_md.read_text()
        all_refs.update(re.findall(r"`\.claude/context/([\w-]+\.md)`", text))

    for context_file in sorted(CONTEXT_DIR.glob("*.md")):
        if context_file.name in all_refs:
            ok(f"context/{context_file.name} — referenced")
        else:
            warn(
                f"context/{context_file.name} exists but is not referenced in any "
                f"CLAUDE.md or AGENT.md — add a reference or remove the file"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Insights IDE context drift check")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on warnings as well as errors",
    )
    args = parser.parse_args()

    print("Insights IDE — Context Drift Check")
    print("=" * 40)

    check_constitution_exists()
    check_key_files()
    check_agent_specs()
    check_agent_context_references()
    check_constitution_context_references()
    check_orphan_context_docs()

    # Summary
    print("\n" + "=" * 40)
    print("Summary")
    print("=" * 40)

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(w)

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(e)

    if not errors and not warnings:
        print("\nAll checks passed. Knowledge layer is consistent.")
        return 0

    if not errors:
        print(f"\n{len(warnings)} warning(s), 0 errors.")
        return 1 if args.strict else 0

    print(f"\n{len(warnings)} warning(s), {len(errors)} error(s). Fix errors before proceeding.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
