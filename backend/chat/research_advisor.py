"""ResearchAdvisor — research question to method recommendation.

Implements Stages 1-3 of the progressive refinement pipeline (ADR-005):

1. **characterize_problem** — research question + data context -> ProblemProfile
2. **match_candidates** — ProblemProfile + block registry -> ranked MethodCandidates
3. **recommend** — candidates + constraints -> selected method + rationale

Phase 3 milestone: all methods return structured placeholders.  Full LLM
integration will replace the placeholder logic in each method body.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from reasoning.profiles import ReasoningProfile

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SituationalContext(BaseModel):
    """Practical circumstances inferred from the research brief.

    These are natural-language descriptions (not enums) that the LLM reasons
    over during Stage 2 contextual matching.  All fields are optional because
    the user may not provide every detail.
    """

    available_data: str | None = None
    hypothesis_state: str | None = None
    time_constraint: str | None = None
    epistemic_stance: str | None = None
    deliverable_expectation: str | None = None


class ProblemProfile(BaseModel):
    """Stage 1 output: analytical character + practical circumstances.

    ``dimensions`` carries the formal ordinal labels used for mechanical
    filtering.  ``situational_context`` carries free-text descriptions used
    for LLM contextual reasoning.  These must remain separate fields.
    """

    research_question: str
    dimensions: dict[str, str]
    situational_context: SituationalContext
    reasoning: str


class MethodCandidate(BaseModel):
    """A ranked candidate method produced by Stage 2."""

    block_implementation: str
    block_type: str
    fit_score: float
    fit_reasoning: str
    tradeoffs: str
    dimensions: dict[str, str]


class Recommendation(BaseModel):
    """Stage 3 output: selected method with rationale and optional sketch."""

    selected_method: str
    rationale: str
    pipeline_sketch: dict[str, Any] | None = None
    practitioner_workflow: str | None = None


# ---------------------------------------------------------------------------
# ResearchAdvisor
# ---------------------------------------------------------------------------


class ResearchAdvisor:
    """Research question -> method recommendation.

    Stages 1-3 of progressive refinement (ADR-005).
    Phase 3 milestone: implement LLM calls in each method.
    """

    def __init__(self, block_registry, reasoning_profile: ReasoningProfile) -> None:
        self.registry = block_registry
        self.profile = reasoning_profile

    # -- Stage 1 -------------------------------------------------------------

    async def characterize_problem(
        self,
        research_question: str,
        data_context: dict | None = None,
    ) -> ProblemProfile:
        """Stage 1: research question + data context -> ProblemProfile.

        Placeholder implementation.  Will be replaced with LLM-based
        characterization that maps the question to dimensional labels and
        infers situational context from the research brief.
        """
        return ProblemProfile(
            research_question=research_question,
            dimensions={
                "exploratory_confirmatory": "exploratory",
                "assumption_weight": "low",
                "output_interpretability": "medium",
                "sample_sensitivity": "low",
                "reproducibility": "medium",
                "data_structure_affinity": "mixed",
            },
            situational_context=SituationalContext(
                available_data=data_context.get("available_data") if data_context else None,
            ),
            reasoning="[placeholder] Characterization not yet implemented.",
        )

    # -- Stage 2 -------------------------------------------------------------

    async def match_candidates(
        self,
        profile: ProblemProfile,
    ) -> list[MethodCandidate]:
        """Stage 2: ProblemProfile + block registry -> ranked candidates.

        Placeholder implementation.  Will be replaced with dimensional
        filtering over the block registry followed by LLM ranking informed
        by situational context.
        """
        return [
            MethodCandidate(
                block_implementation="placeholder_analysis",
                block_type="analysis",
                fit_score=0.5,
                fit_reasoning="[placeholder] Matching not yet implemented.",
                tradeoffs="[placeholder] Tradeoff analysis not yet implemented.",
                dimensions={},
            ),
        ]

    # -- Stage 3 -------------------------------------------------------------

    async def recommend(
        self,
        candidates: list[MethodCandidate],
        constraints: dict | None = None,
    ) -> Recommendation:
        """Stage 3: candidates + constraints -> selected method + rationale.

        Placeholder implementation.  Will be replaced with LLM-based
        selection that considers practitioner workflows, reasoning profile
        preferences, and user-supplied constraints.
        """
        selected = candidates[0].block_implementation if candidates else "none"
        return Recommendation(
            selected_method=selected,
            rationale="[placeholder] Recommendation not yet implemented.",
            pipeline_sketch=None,
            practitioner_workflow=None,
        )
