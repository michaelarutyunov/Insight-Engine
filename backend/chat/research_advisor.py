"""ResearchAdvisor — research question to method recommendation.

Implements Stages 1-3 of the progressive refinement pipeline (ADR-005):

1. **characterize_problem** — research question + data context -> ProblemProfile
2. **match_candidates** — ProblemProfile + block registry -> ranked MethodCandidates
3. **recommend** — candidates + constraints -> selected method + rationale + pipeline_sketch

Stage 1 uses an LLM call via AsyncAnthropic to infer dimensional labels and
situational context from the research question.  Stage 2 uses mechanical
dimensional filtering followed by LLM-based contextual ranking.  Stage 3 uses
an LLM call that considers practitioner workflows, reasoning profile
preferences, and user-supplied constraints to select a method and produce a
pipeline sketch.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

from chat.context_builder import build_advisor_context
from reasoning.dimensions import ALLOWED_VALUES, validate_dimensions
from reasoning.profiles import ReasoningProfile

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# Default model for the LLM call — can be overridden per-instance.
_DEFAULT_MODEL = "claude-sonnet-4-6"

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
    Stage 1 and Stage 2 use live LLM calls; Stage 3 remains a placeholder.
    """

    def __init__(
        self,
        block_registry: Any,
        reasoning_profile: ReasoningProfile,
        *,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        self.registry = block_registry
        self.profile = reasoning_profile
        self.model = model
        self._client = anthropic.AsyncAnthropic()

    # -- Stage 1 -------------------------------------------------------------

    def _build_characterize_system_prompt(self) -> str:
        """Build the system prompt for Stage 1 characterization.

        Uses ``build_advisor_context()`` to include the reasoning profile's
        dimension weights and methodological preferences alongside the fixed
        dimension definitions and situational attribute vocabulary.
        """
        lines: list[str] = [
            "You are a research methodology expert. Your task is to characterize"
            " a research question by assigning dimensional labels and inferring"
            " situational context.",
            "",
            "## Reasoning Profile Context",
            "",
        ]

        # Inject the advisor context (profile weights + preferences) so the
        # LLM knows which dimensions matter most and what methodological stance
        # to lean toward.
        profile_context = build_advisor_context(self.profile, candidates=None)
        lines.append(profile_context)
        lines.append("")

        lines += [
            "## Dimension Definitions",
            "",
            "Assign exactly one value from the allowed set for each of the six"
            " methodological dimensions:",
            "",
        ]
        for dim_key, allowed in ALLOWED_VALUES.items():
            lines.append(f"- **{dim_key}**: {', '.join(sorted(allowed))}")
        lines.append("")

        lines += [
            "## Situational Context Fields",
            "",
            "Infer practical circumstances from the research question and data"
            " context.  Each field is a short natural-language description"
            " (not an enum).  Use null if the information is not available.",
            "",
            "- **available_data**: What data the researcher has access to"
            '  (e.g. "NPS survey with verbatims, no operational data").',
            "- **hypothesis_state**: Whether a hypothesis exists"
            '  (e.g. "no prior hypothesis", "suspected cause",'
            ' "known event, unknown mechanism").',
            '- **time_constraint**: Practical timeline  (e.g. "days", "weeks", "months").',
            "- **epistemic_stance**: Methodological philosophy"
            '  (e.g. "trust existing frameworks", "suspect unknown unknowns",'
            ' "question measurement validity").',
            "- **deliverable_expectation**: What the stakeholder needs"
            '  (e.g. "board-ready quantified answer", "exploratory landscape",'
            ' "actionable intervention").',
            "",
            "## Output Format",
            "",
            "Return a single JSON object with exactly these keys:",
            "",
            "```json",
            "{",
            '  "dimensions": {',
            '    "exploratory_confirmatory": "<value>",',
            '    "assumption_weight": "<value>",',
            '    "output_interpretability": "<value>",',
            '    "sample_sensitivity": "<value>",',
            '    "reproducibility": "<value>",',
            '    "data_structure_affinity": "<value>"',
            "  },",
            '  "situational_context": {',
            '    "available_data": "<value or null>",',
            '    "hypothesis_state": "<value or null>",',
            '    "time_constraint": "<value or null>",',
            '    "epistemic_stance": "<value or null>",',
            '    "deliverable_expectation": "<value or null>"',
            "  },",
            '  "reasoning": "<1-3 sentence explanation of why you chose these values>"',
            "}",
            "```",
            "",
            "All six dimension keys must be present.  All dimension values must"
            " come from the allowed sets listed above.  Situational context fields"
            " may be null if not inferable.",
        ]
        return "\n".join(lines)

    def _build_characterize_user_message(
        self,
        research_question: str,
        data_context: dict | None,
    ) -> str:
        """Build the user message for Stage 1."""
        parts: list[str] = [
            f"Research question: {research_question}",
        ]
        if data_context:
            context_lines = [f"  {k}: {v}" for k, v in data_context.items()]
            parts.append("Data context:")
            parts.extend(context_lines)
        return "\n".join(parts)

    def _parse_characterize_response(
        self,
        raw_text: str,
        research_question: str,
    ) -> ProblemProfile:
        """Parse the LLM JSON response into a validated ProblemProfile.

        Raises ``ValueError`` if the response cannot be parsed or dimensions
        are invalid.
        """
        # Strip markdown fences if the LLM wrapped them.
        text = raw_text.strip()
        if text.startswith("```"):
            first_newline = text.index("\n") if "\n" in text else len(text)
            text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM response is not valid JSON: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("LLM response is not a JSON object")

        # Extract and validate dimensions.
        dims = data.get("dimensions", {})
        if not isinstance(dims, dict):
            raise ValueError("'dimensions' must be a JSON object")

        if not validate_dimensions(dims):
            raise ValueError(f"Invalid dimensions in LLM response: {dims}")

        # Ensure all 6 dimension keys are present.
        missing = set(ALLOWED_VALUES.keys()) - set(dims.keys())
        if missing:
            raise ValueError(f"Missing dimension keys: {sorted(missing)}")

        # Extract reasoning.
        reasoning = data.get("reasoning", "")
        if not isinstance(reasoning, str):
            reasoning = str(reasoning)

        # Parse situational context.
        sc_data = data.get("situational_context", {})
        if not isinstance(sc_data, dict):
            raise ValueError("'situational_context' must be a JSON object")

        try:
            situational_context = SituationalContext(**sc_data)
        except ValidationError as exc:
            raise ValueError(f"Invalid situational context: {exc}") from exc

        return ProblemProfile(
            research_question=research_question,
            dimensions=dims,
            situational_context=situational_context,
            reasoning=reasoning,
        )

    async def characterize_problem(
        self,
        research_question: str,
        data_context: dict | None = None,
    ) -> ProblemProfile:
        """Stage 1: research question + data context -> ProblemProfile.

        Uses an AsyncAnthropic LLM call with structured JSON output.  The system
        prompt includes dimension definitions and situational attribute
        vocabulary.  The response is parsed, validated, and returned as a
        ProblemProfile.
        """
        system_prompt = self._build_characterize_system_prompt()
        user_message = self._build_characterize_user_message(research_question, data_context)

        response = await self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        # Extract text from the response content blocks.
        raw_text = ""
        for block in response.content:
            if isinstance(block, anthropic.types.TextBlock):
                raw_text += block.text

        return self._parse_characterize_response(raw_text, research_question)

    # -- Stage 2 -------------------------------------------------------------

    # Dimension-specific adjacency / matching rules.

    # For data_structure_affinity, exact match is required.
    _STRICT_DIMENSIONS: set[str] = {"data_structure_affinity"}

    # exploratory_confirmatory uses a 3-value ordinal where adjacency is allowed.
    _EXPLORATORY_ORDER: list[str] = ["exploratory", "mixed", "confirmatory"]

    # All other ordinal dimensions use low/medium/high ordering.
    _ORDINAL_ORDER: list[str] = ["low", "medium", "high"]

    def _mechanical_filter(
        self,
        profile: ProblemProfile,
    ) -> list[dict[str, Any]]:
        """Filter Analysis blocks from the registry by dimensional compatibility.

        Iterates all registered blocks, keeps only those with
        ``block_type == "analysis"``, and then applies dimensional matching
        rules:

        - **data_structure_affinity**: exact match required.
        - **exploratory_confirmatory**: adjacent values allowed
          (exploratory <-> mixed <-> confirmatory).
        - All other dimensions: ordinal distance of at most 1 step
          (low <-> medium <-> high).

        Returns a list of block info dicts with an added
        ``_compatibility_score`` field (0.0-1.0) indicating how closely the
        block's dimensions match the profile.
        """
        all_blocks: list[dict[str, Any]]
        if hasattr(self.registry, "list_blocks"):
            all_blocks = self.registry.list_blocks()
        elif isinstance(self.registry, list):
            all_blocks = self.registry
        else:
            all_blocks = []

        results: list[dict[str, Any]] = []

        for block in all_blocks:
            if block.get("block_type") != "analysis":
                continue

            block_dims = block.get("dimensions", {})
            if not block_dims:
                # Blocks without dimensions cannot be matched dimensionally.
                continue

            if not self._dimensions_compatible(profile.dimensions, block_dims):
                continue

            score = self._compute_compatibility_score(profile.dimensions, block_dims)
            entry = {**block, "_compatibility_score": score}
            results.append(entry)

        # Sort by compatibility score descending.
        results.sort(key=lambda b: b.get("_compatibility_score", 0.0), reverse=True)
        return results

    def _dimensions_compatible(
        self,
        profile_dims: dict[str, str],
        block_dims: dict[str, str],
    ) -> bool:
        """Return True if every populated profile dimension is compatible."""
        for dim_key, profile_val in profile_dims.items():
            if profile_val is None:
                continue
            block_val = block_dims.get(dim_key)
            if block_val is None:
                continue

            if dim_key in self._STRICT_DIMENSIONS:
                if profile_val != block_val:
                    return False
            elif dim_key == "exploratory_confirmatory":
                if not self._adjacent(profile_val, block_val, self._EXPLORATORY_ORDER):
                    return False
            else:
                # Default ordinal dimension.
                if not self._adjacent(profile_val, block_val, self._ORDINAL_ORDER):
                    return False
        return True

    @staticmethod
    def _adjacent(a: str, b: str, order: list[str]) -> bool:
        """Return True if ``a`` and ``b`` are the same or adjacent in *order*."""
        try:
            idx_a = order.index(a)
            idx_b = order.index(b)
            return abs(idx_a - idx_b) <= 1
        except ValueError:
            # Unknown value — only match exactly.
            return a == b

    def _compute_compatibility_score(
        self,
        profile_dims: dict[str, str],
        block_dims: dict[str, str],
    ) -> float:
        """Compute a 0.0-1.0 compatibility score between two dimension sets.

        For each dimension that both sides declare, the score contribution is
        ``1 - distance / max_distance``.  The final score is the average of
        all individual dimension scores.
        """
        scores: list[float] = []
        for dim_key, profile_val in profile_dims.items():
            if profile_val is None:
                continue
            block_val = block_dims.get(dim_key)
            if block_val is None:
                continue

            if profile_val == block_val:
                scores.append(1.0)
                continue

            # Determine order list for this dimension.
            if dim_key == "exploratory_confirmatory":
                order = self._EXPLORATORY_ORDER
            elif dim_key in self._STRICT_DIMENSIONS:
                # Strict dimensions that don't match get score 0.
                scores.append(0.0)
                continue
            else:
                order = self._ORDINAL_ORDER

            try:
                idx_p = order.index(profile_val)
                idx_b = order.index(block_val)
                max_dist = len(order) - 1
                dist = abs(idx_p - idx_b)
                scores.append(1.0 - dist / max_dist if max_dist > 0 else 0.0)
            except ValueError:
                scores.append(0.0)

        return sum(scores) / len(scores) if scores else 0.0

    def _build_rank_prompt(
        self,
        filtered_blocks: list[dict[str, Any]],
        profile: ProblemProfile,
    ) -> tuple[str, str]:
        """Build system + user prompts for the LLM ranking call.

        Returns a ``(system_prompt, user_message)`` tuple.
        """
        system_lines: list[str] = [
            "You are a research methodology expert. Your task is to rank"
            " analysis methods by contextual fit for a given research problem.",
            "",
            "## Ranking Criteria",
            "",
            "Consider the following when ranking:",
            "1. How well the method's dimensional profile matches the problem.",
            "2. Whether the method is appropriate given the situational context"
            " (available data, hypothesis state, time constraints, etc.).",
            "3. Practical tradeoffs the researcher should be aware of.",
            "",
            "## Output Format",
            "",
            "Return a JSON array with 3-6 ranked candidates. Each entry must have:",
            "",
            "```json",
            "[",
            "  {",
            '    "block_implementation": "<implementation name>",',
            '    "fit_score": <0.0-1.0>,',
            '    "fit_reasoning": "<1-2 sentences why this method fits>",',
            '    "tradeoffs": "<1-2 sentences about limitations or tradeoffs>"',
            "  }",
            "]",
            "```",
            "",
            "Rank by descending fit_score.  The top candidate should be the best"
            " contextual match, not just the best dimensional match.",
        ]
        system_prompt = "\n".join(system_lines)

        # Build user message with profile + filtered block descriptions.
        user_parts: list[str] = [
            "## Research Problem",
            "",
            f"Question: {profile.research_question}",
            "",
            "### Dimensional Profile",
            "",
        ]
        for dim_key, value in profile.dimensions.items():
            user_parts.append(f"- **{dim_key}**: {value}")

        user_parts.append("")
        user_parts.append("### Situational Context")
        user_parts.append("")
        sc = profile.situational_context
        if sc.available_data:
            user_parts.append(f"- Available data: {sc.available_data}")
        if sc.hypothesis_state:
            user_parts.append(f"- Hypothesis state: {sc.hypothesis_state}")
        if sc.time_constraint:
            user_parts.append(f"- Time constraint: {sc.time_constraint}")
        if sc.epistemic_stance:
            user_parts.append(f"- Epistemic stance: {sc.epistemic_stance}")
        if sc.deliverable_expectation:
            user_parts.append(f"- Deliverable expectation: {sc.deliverable_expectation}")

        user_parts.append("")
        user_parts.append(f"## Candidate Methods ({len(filtered_blocks)} filtered)")
        user_parts.append("")

        for idx, block in enumerate(filtered_blocks, 1):
            impl = block.get("block_implementation", "unknown")
            desc = block.get("description", "No description.")
            notes = block.get("methodological_notes", "")
            dims = block.get("dimensions", {})
            score = block.get("_compatibility_score", 0.0)

            user_parts.append(f"### {idx}. {impl}")
            user_parts.append(f"Description: {desc}")
            user_parts.append(f"Compatibility score: {score:.2f}")
            if dims:
                dim_parts = [f"{k}={v}" for k, v in dims.items()]
                user_parts.append(f"Dimensions: {{{', '.join(dim_parts)}}}")
            if notes:
                # Include first 500 chars of methodological notes for context.
                truncated = notes[:500] + ("..." if len(notes) > 500 else "")
                user_parts.append(f"Methodological notes: {truncated}")
            user_parts.append("")

        user_parts.append("Rank these candidates by contextual fit. Return 3-6 candidates.")

        user_message = "\n".join(user_parts)
        return system_prompt, user_message

    def _parse_rank_response(
        self,
        raw_text: str,
        filtered_blocks: list[dict[str, Any]],
    ) -> list[MethodCandidate]:
        """Parse the LLM ranking response into MethodCandidate objects.

        Validates that referenced block_implementations exist in the filtered
        set, and attaches the block's dimensional profile.
        """
        # Strip markdown fences.
        text = raw_text.strip()
        if text.startswith("```"):
            first_newline = text.index("\n") if "\n" in text else len(text)
            text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning("LLM rank response is not valid JSON: %s", exc)
            return self._fallback_candidates(filtered_blocks)

        if not isinstance(data, list):
            logger.warning("LLM rank response is not a JSON array")
            return self._fallback_candidates(filtered_blocks)

        # Build lookup from implementation name -> block info.
        block_lookup: dict[str, dict[str, Any]] = {}
        for block in filtered_blocks:
            impl = block.get("block_implementation", "")
            if impl:
                block_lookup[impl] = block

        candidates: list[MethodCandidate] = []
        for entry in data[:6]:  # Cap at 6 candidates.
            if not isinstance(entry, dict):
                continue

            impl_name = entry.get("block_implementation", "")
            if not impl_name or impl_name not in block_lookup:
                continue

            block_info = block_lookup[impl_name]
            fit_score = entry.get("fit_score", 0.5)
            if not isinstance(fit_score, (int, float)):
                fit_score = 0.5
            fit_score = max(0.0, min(1.0, float(fit_score)))

            candidates.append(
                MethodCandidate(
                    block_implementation=impl_name,
                    block_type=block_info.get("block_type", "analysis"),
                    fit_score=fit_score,
                    fit_reasoning=str(entry.get("fit_reasoning", "")),
                    tradeoffs=str(entry.get("tradeoffs", "")),
                    dimensions=block_info.get("dimensions", {}),
                )
            )

        return candidates

    @staticmethod
    def _fallback_candidates(
        filtered_blocks: list[dict[str, Any]],
    ) -> list[MethodCandidate]:
        """Produce fallback candidates when LLM ranking fails.

        Returns the top 3 blocks by mechanical compatibility score.
        """
        results: list[MethodCandidate] = []
        for block in filtered_blocks[:3]:
            results.append(
                MethodCandidate(
                    block_implementation=block.get("block_implementation", "unknown"),
                    block_type=block.get("block_type", "analysis"),
                    fit_score=float(block.get("_compatibility_score", 0.5)),
                    fit_reasoning="[mechanical fallback] Ranked by dimensional compatibility only.",
                    tradeoffs="[mechanical fallback] LLM ranking unavailable; contextual fit not assessed.",
                    dimensions=block.get("dimensions", {}),
                )
            )
        return results

    async def match_candidates(
        self,
        profile: ProblemProfile,
    ) -> list[MethodCandidate]:
        """Stage 2: ProblemProfile + block registry -> ranked MethodCandidates.

        Two-step process:

        1. **Mechanical filter** — narrow Analysis blocks by dimensional
           compatibility (exact match for ``data_structure_affinity``,
           adjacent values for ordinal dimensions).
        2. **LLM ranking** — rank the filtered blocks by contextual fit
           using situational context from the ProblemProfile.

        Returns 3-6 :class:`MethodCandidate` objects sorted by fit_score.
        If the LLM call fails, falls back to mechanical scores only.
        """
        # Step 1: Mechanical filter.
        filtered = self._mechanical_filter(profile)
        logger.info(
            "Mechanical filter: %d analysis blocks passed from registry",
            len(filtered),
        )

        if not filtered:
            return []

        # Step 2: LLM ranking (only if we have candidates to rank).
        system_prompt, user_message = self._build_rank_prompt(filtered, profile)

        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            raw_text = ""
            for block in response.content:
                if isinstance(block, anthropic.types.TextBlock):
                    raw_text += block.text

            candidates = self._parse_rank_response(raw_text, filtered)

            if not candidates:
                logger.warning("LLM ranking returned no valid candidates; using fallback")
                candidates = self._fallback_candidates(filtered)

            return candidates[:6]

        except Exception:
            logger.exception("LLM ranking call failed; using mechanical fallback")
            return self._fallback_candidates(filtered)

    # -- Stage 3 -------------------------------------------------------------

    def _build_recommend_system_prompt(self) -> str:
        """Build the system prompt for Stage 3 method selection.

        The LLM's task is to select the best method from the candidates,
        considering the reasoning profile preferences, practitioner
        workflow guidance, and user constraints.
        """
        lines: list[str] = [
            "You are a research methodology expert. Your task is to select the"
            " best analytical method from a list of ranked candidates and"
            " produce a recommendation with rationale and a rough pipeline sketch.",
            "",
            "## Selection Criteria",
            "",
            "Consider the following when selecting:",
            "1. Fit with the reasoning profile's dimensional weights and preferences.",
            "2. Alignment with practitioner workflow guidance (if available).",
            "3. User-specified constraints (timeline, budget, team skills, etc.).",
            "4. Practical tradeoffs and limitations of each method.",
            "",
            "## Output Format",
            "",
            "Return a single JSON object with exactly these keys:",
            "",
            "```json",
            "{",
            '  "selected_method": "<block_implementation name of selected method>",',
            '  "rationale": "<2-4 sentences explaining why this method was selected>",',
            '  "pipeline_sketch": {',
            '    "nodes": [',
            '      {"type": "<block_type>", "implementation": "<block_implementation>", "purpose": "<brief description>"',
            "      }",
            "    ],",
            '    "connections": [',
            '      {"from": "<node_index>", "to": "<node_index>", "data_type": "<edge_type>"',
            "      }",
            "    ]",
            "  }",
            "}",
            "```",
            "",
            "The pipeline_sketch is a rough outline, not a full pipeline definition.",
            " It should include:",
            "- nodes: Array of likely block types (source, transform, analysis, etc.)",
            "- connections: Array of data flow connections between nodes",
            "- Use node indices (0-based) in the connections to reference nodes",
            "",
            "Common edge data types: respondent_collection, segment_profile_set,",
            " concept_brief_set, evaluation_set, text_corpus, persona_set, generic_blob",
        ]
        return "\n".join(lines)

    def _build_recommend_user_message(
        self,
        candidates: list[MethodCandidate],
        constraints: dict | None,
    ) -> str:
        """Build the user message for Stage 3 recommendation."""
        # Convert candidates to dicts for context builder
        candidate_dicts = [c.model_dump() for c in candidates]

        # Build advisor context (includes profile, candidates, and workflow)
        base_dir = Path(__file__).resolve().parent.parent.parent / "reasoning_profiles"
        advisor_context = build_advisor_context(self.profile, candidate_dicts, base_dir=base_dir)

        parts: list[str] = [
            "Select the best method from the candidates below.",
            "",
            advisor_context,
            "",
        ]

        # Add constraints if provided
        if constraints:
            parts.append("## User Constraints")
            parts.append("")
            for key, value in constraints.items():
                parts.append(f"- **{key}**: {value}")
            parts.append("")

        parts.append("Select the best method and provide your recommendation with pipeline sketch.")

        return "\n".join(parts)

    def _parse_recommend_response(
        self,
        raw_text: str,
        candidates: list[MethodCandidate],
    ) -> Recommendation:
        """Parse the LLM response into a Recommendation object.

        Validates that the selected_method is one of the candidates.
        Extracts practitioner_workflow name from the selected method.
        """
        # Strip markdown fences
        text = raw_text.strip()
        if text.startswith("```"):
            first_newline = text.index("\n") if "\n" in text else len(text)
            text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning("LLM recommend response is not valid JSON: %s", exc)
            # Fallback to top candidate
            top = candidates[0] if candidates else None
            return Recommendation(
                selected_method=top.block_implementation if top else "none",
                rationale=f"[parse error] LLM response was not valid JSON: {exc}",
                pipeline_sketch=None,
                practitioner_workflow=None,
            )

        if not isinstance(data, dict):
            logger.warning("LLM recommend response is not a JSON object")
            top = candidates[0] if candidates else None
            return Recommendation(
                selected_method=top.block_implementation if top else "none",
                rationale="[parse error] Response was not a JSON object",
                pipeline_sketch=None,
                practitioner_workflow=None,
            )

        # Extract selected method
        selected = data.get("selected_method", "")
        if not selected or not isinstance(selected, str):
            logger.warning("Missing or invalid selected_method in LLM response")
            selected = candidates[0].block_implementation if candidates else "none"

        # Validate that selected method is in candidates
        valid_impls = {c.block_implementation for c in candidates}
        if selected not in valid_impls:
            logger.warning(
                "Selected method '%s' not in candidate list; using top candidate",
                selected,
            )
            selected = candidates[0].block_implementation if candidates else "none"

        # Extract rationale
        rationale = data.get("rationale", "")
        if not isinstance(rationale, str):
            rationale = str(rationale)

        # Extract pipeline sketch
        sketch = data.get("pipeline_sketch")
        if sketch is not None and not isinstance(sketch, dict):
            logger.warning("pipeline_sketch is not a dict; setting to None")
            sketch = None

        # Extract practitioner workflow from selected candidate
        practitioner_workflow = None
        for cand in candidates:
            if cand.block_implementation == selected:
                # Derive workflow name from block implementation
                # e.g., "segmentation_kmeans" -> "segmentation"
                # If no underscore, use the full implementation name
                if "_" in cand.block_implementation:
                    block_family = cand.block_implementation.split("_")[0]
                else:
                    block_family = cand.block_implementation
                practitioner_workflow = f"{block_family}.md"
                break

        return Recommendation(
            selected_method=selected,
            rationale=rationale,
            pipeline_sketch=sketch,
            practitioner_workflow=practitioner_workflow,
        )

    async def recommend(
        self,
        candidates: list[MethodCandidate],
        constraints: dict | None = None,
    ) -> Recommendation:
        """Stage 3: candidates + constraints -> selected method + rationale.

        Uses an LLM call that considers:
        - Candidate methods (from Stage 2)
        - Reasoning profile preferences (dimension weights, methodological stance)
        - Practitioner workflow for the top candidate (loaded via reasoning.workflows)
        - User-specified constraints (timeline, budget, team skills, etc.)

        Returns a Recommendation with:
        - selected_method: The chosen block_implementation name
        - rationale: 2-4 sentences explaining the selection
        - pipeline_sketch: Rough node/connection outline (not full pipeline JSON)
        - practitioner_workflow: Name of the workflow file (e.g., "segmentation.md")

        If the LLM call fails, falls back to the top-ranked candidate from Stage 2.
        """
        if not candidates:
            return Recommendation(
                selected_method="none",
                rationale="No candidates provided to recommend from.",
                pipeline_sketch=None,
                practitioner_workflow=None,
            )

        system_prompt = self._build_recommend_system_prompt()
        user_message = self._build_recommend_user_message(candidates, constraints)

        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            raw_text = ""
            for block in response.content:
                if isinstance(block, anthropic.types.TextBlock):
                    raw_text += block.text

            return self._parse_recommend_response(raw_text, candidates)

        except Exception:
            logger.exception("LLM recommend call failed; using top candidate fallback")
            top = candidates[0]
            if "_" in top.block_implementation:
                block_family = top.block_implementation.split("_")[0]
            else:
                block_family = top.block_implementation
            return Recommendation(
                selected_method=top.block_implementation,
                rationale=(
                    f"[LLM fallback] Using top-ranked candidate from Stage 2. "
                    f"Fit score: {top.fit_score:.2f}. {top.fit_reasoning}"
                ),
                pipeline_sketch=None,
                practitioner_workflow=f"{block_family}.md",
            )
