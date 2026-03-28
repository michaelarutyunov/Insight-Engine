"""Loop controller -- iteration tracking and termination logic for pipeline loops.

The executor delegates all loop-related decisions to this module. The controller
is a pure-logic class with no I/O: the executor handles persistence of the
serialised state (e.g. for HITL suspend/resume).
"""

from __future__ import annotations

from pydantic import BaseModel


class LoopDefinition(BaseModel):
    """Internal representation of a single loop, parsed from pipeline schema."""

    loop_id: str
    entry_node: str
    exit_node: str
    termination_type: str  # router_condition | max_iterations | hitl
    max_iterations: int | None = None
    fallback: str | None = None  # hitl | abort (used when max_iterations is reached)
    current_iteration: int = 0


class LoopError(Exception):
    """Raised when a loop termination triggers abort or an undefined loop is referenced."""


class LoopController:
    """Track loop iterations and decide whether a loop should continue.

    Public API:
    - __init__(loop_definitions)
    - should_continue(loop_id, router_decision=None) -> bool
    - increment(loop_id) -> None
    - get_state() -> dict
    - restore_state(state: dict) -> None
    """

    def __init__(self, loop_definitions: list[dict]) -> None:
        """Build the loop map from pipeline loop_definitions.

        Each dict is expected to contain the fields serialised by
        LoopSchema, i.e. loop_id, entry_node, exit_node,
        and termination (a nested dict with type, optional max_iterations,
        and optional fallback).
        """
        self._loops: dict[str, LoopDefinition] = {}
        for raw in loop_definitions:
            termination = raw["termination"]
            if isinstance(termination, dict):
                term_type = termination["type"]
                max_iters = termination.get("max_iterations")
                fallback = termination.get("fallback")
            else:
                # Already a TerminationSchema-like object with attributes
                term_type = termination.type
                max_iters = getattr(termination, "max_iterations", None)
                fallback = getattr(termination, "fallback", None)

            loop_id = str(raw["loop_id"])
            self._loops[loop_id] = LoopDefinition(
                loop_id=loop_id,
                entry_node=str(raw["entry_node"]),
                exit_node=str(raw["exit_node"]),
                termination_type=term_type,
                max_iterations=max_iters,
                fallback=fallback,
            )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def has_loop(self, loop_id: str) -> bool:
        """Return True if the given loop_id is registered."""
        return loop_id in self._loops

    def get_entry_node(self, loop_id: str) -> str:
        """Return the entry node ID for a loop.

        Raises LoopError if loop_id is unknown.
        """
        self._require_loop(loop_id)
        return self._loops[loop_id].entry_node

    def get_exit_node(self, loop_id: str) -> str:
        """Return the exit node ID for a loop.

        Raises LoopError if loop_id is unknown.
        """
        self._require_loop(loop_id)
        return self._loops[loop_id].exit_node

    # ------------------------------------------------------------------
    # Core loop logic
    # ------------------------------------------------------------------

    def increment(self, loop_id: str) -> None:
        """Increment the iteration counter for loop_id.

        Raises LoopError if loop_id is unknown.
        """
        self._require_loop(loop_id)
        self._loops[loop_id].current_iteration += 1

    def should_continue(self, loop_id: str, router_decision: str | None = None) -> bool:
        """Decide whether the loop should iterate again.

        Returns True if the loop should continue, False if it should exit.

        Termination logic by type:
        - router_condition: delegates to the router_decision parameter.
          "continue" means keep looping, anything else means exit.
        - hitl: always returns False -- execution suspends for a human
          decision. The executor is expected to trigger HITL suspend.
        - max_iterations: if the counter has reached the limit, consult the
          fallback strategy ("hitl" suspends, "abort" raises LoopError).
          If not yet at the limit, returns True.

        Raises:
            LoopError: if loop_id is unknown or if an abort fallback fires.
        """
        self._require_loop(loop_id)
        loop = self._loops[loop_id]

        if loop.termination_type == "router_condition":
            return router_decision == "continue"

        if loop.termination_type == "hitl":
            # Always suspend -- executor handles HITL flow.
            return False

        if loop.termination_type == "max_iterations":
            if loop.max_iterations is not None and loop.current_iteration >= loop.max_iterations:
                return self._handle_max_reached(loop)
            return True

        # Unknown termination type -- treat as exit.
        return False

    # ------------------------------------------------------------------
    # Serialisation for HITL suspend / resume
    # ------------------------------------------------------------------

    def get_state(self) -> dict:
        """Return a JSON-serialisable snapshot of all loop states.

        The dict maps loop_id to a plain dict of the loop fields.
        """
        return {loop_id: loop.model_dump() for loop_id, loop in self._loops.items()}

    def restore_state(self, state: dict) -> None:
        """Restore loop states from a previously serialised snapshot.

        Overwrites all tracked loops. Unknown loop_ids in state are ignored
        (they may have been removed between pipeline versions).
        """
        for loop_id, loop_data in state.items():
            if loop_id in self._loops:
                self._loops[loop_id] = LoopDefinition.model_validate(loop_data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_loop(self, loop_id: str) -> None:
        """Raise LoopError if loop_id is not registered."""
        if loop_id not in self._loops:
            raise LoopError(f"Undefined loop_id: {loop_id!r}")

    def _handle_max_reached(self, loop: LoopDefinition) -> bool:
        """Handle the case where max_iterations has been reached.

        - fallback="hitl": return False to signal suspend.
        - fallback="abort" or None: raise LoopError.
        """
        if loop.fallback == "hitl":
            return False
        raise LoopError(
            f"Loop {loop.loop_id!r} reached max_iterations={loop.max_iterations} "
            f"with fallback={loop.fallback!r}"
        )
