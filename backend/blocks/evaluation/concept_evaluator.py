"""Concept Evaluation block — evaluates concepts from persona perspectives using an LLM."""

from typing import Any

from blocks._llm_client import call_llm_json
from blocks.base import EvaluationBase

DEFAULT_DIMENSIONS = ["appeal", "uniqueness", "purchase_intent", "clarity"]
DEFAULT_SCORING_SCALE = {"min": 1, "max": 5}
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_TEMPERATURE = 0.3


class ConceptEvaluation(EvaluationBase):
    """Evaluates product concepts from synthetic persona perspectives using an LLM.

    Produces structured scores across configurable dimensions.
    Requires both concept briefs and personas as inputs.
    """

    @property
    def input_schemas(self) -> list[str]:
        return ["concept_brief_set", "persona_set"]

    @property
    def output_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "default": DEFAULT_MODEL,
                    "description": "LLM model identifier",
                },
                "temperature": {
                    "type": "number",
                    "default": DEFAULT_TEMPERATURE,
                    "description": "Sampling temperature (0.0 to 1.0)",
                },
                "evaluation_dimensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": DEFAULT_DIMENSIONS,
                    "description": "List of dimension names to evaluate on",
                },
                "scoring_scale": {
                    "type": "object",
                    "properties": {
                        "min": {"type": "integer"},
                        "max": {"type": "integer"},
                    },
                    "default": DEFAULT_SCORING_SCALE,
                    "description": "Min and max values for the scoring scale",
                },
            },
            "required": ["evaluation_dimensions"],
        }

    @property
    def description(self) -> str:
        return (
            "Evaluates product concepts from synthetic persona perspectives using an LLM. "
            "Produces structured scores across configurable dimensions. "
            "Requires both concept briefs and personas as inputs."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "Assumes evaluation dimensions are qualitative and require subjective judgment "
            "(e.g., appeal, uniqueness, purchase intent). Requires well-formed concept briefs "
            "with clear value propositions and detailed persona profiles including demographics, "
            "psychographics, and behavioral patterns. The LLM simulates persona perspective-taking, "
            "but outputs are synthetic and should be validated against real human feedback. "
            "Scoring scale must be clearly defined; 1-5 or 1-7 scales are common for concept testing. "
            "Limitations: LLM may not capture cultural nuances or emotional responses accurately; "
            "complex concepts may require more detailed prompts or human-in-the-loop validation. "
            "Alternatives: For large-scale concept screening, consider max-diff conjoint analysis; "
            "for deep qualitative insights, use human focus groups or in-depth interviews."
        )

    @property
    def tags(self) -> list[str]:
        return [
            "concept-testing",
            "persona-simulation",
            "llm-evaluation",
            "qualitative-scoring",
            "product-research",
            "multi-dimensional",
        ]

    def validate_config(self, config: dict) -> bool:
        if "evaluation_dimensions" not in config:
            return False
        dims = config.get("evaluation_dimensions")
        if not isinstance(dims, list) or len(dims) == 0:
            return False
        if not all(isinstance(d, str) for d in dims):
            return False
        if "model" in config and not isinstance(config["model"], str):
            return False
        if "temperature" in config:
            temp = config["temperature"]
            if not isinstance(temp, (int, float)) or not (0.0 <= temp <= 1.0):
                return False
        if "scoring_scale" in config:
            scale = config["scoring_scale"]
            if not isinstance(scale, dict):
                return False
            if "min" not in scale or "max" not in scale:
                return False
            if not isinstance(scale["min"], int) or not isinstance(scale["max"], int):
                return False
            if scale["min"] >= scale["max"]:
                return False
        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        concepts_data = inputs["concept_brief_set"]
        personas_data = inputs["persona_set"]

        concepts = (
            concepts_data.get("concepts", concepts_data)
            if isinstance(concepts_data, dict)
            else concepts_data
        )
        personas = (
            personas_data.get("personas", personas_data)
            if isinstance(personas_data, dict)
            else personas_data
        )

        model = config.get("model", DEFAULT_MODEL)
        temperature = config.get("temperature", DEFAULT_TEMPERATURE)
        dimensions = config.get("evaluation_dimensions", DEFAULT_DIMENSIONS)
        scoring_scale = config.get("scoring_scale", DEFAULT_SCORING_SCALE)
        scale_min = scoring_scale["min"]
        scale_max = scoring_scale["max"]

        evaluations: list[dict[str, Any]] = []

        for concept in concepts:
            for persona in personas:
                concept_id = concept.get("id", concept.get("name", str(concept)))
                persona_id = persona.get("id", persona.get("name", str(persona)))

                system_prompt = self._build_system_prompt(dimensions, scale_min, scale_max)
                user_prompt = self._build_user_prompt(concept, persona, dimensions)

                llm_response = await call_llm_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    temperature=temperature,
                )

                dimensions_scores = self._parse_scores(
                    llm_response, dimensions, scale_min, scale_max
                )
                rationale = llm_response.get("rationale", "")

                evaluations.append(
                    {
                        "concept_id": concept_id,
                        "persona_id": persona_id,
                        "dimensions": dimensions_scores,
                        "rationale": rationale,
                    }
                )

        return {"evaluation_set": {"evaluations": evaluations}}

    def _build_system_prompt(self, dimensions: list[str], scale_min: int, scale_max: int) -> str:
        dims_list = ", ".join(dimensions)
        return (
            f"You are a research analyst evaluating product concepts from the perspective "
            f"of different consumer personas. For each concept-persona pair, provide scores "
            f"on the following dimensions: {dims_list}. "
            f"Score each dimension on a scale from {scale_min} to {scale_max}, "
            f"where {scale_min} is the lowest and {scale_max} is the highest. "
            f"Also provide a brief rationale explaining the scores."
        )

    def _build_user_prompt(self, concept: dict, persona: dict, dimensions: list[str]) -> str:
        dims_list = ", ".join(dimensions)
        return (
            f"Please evaluate the following product concept from the perspective "
            f"of the given persona.\n\n"
            f"## Concept\n{concept}\n\n"
            f"## Persona\n{persona}\n\n"
            f"Provide scores for: {dims_list}\n"
            f'Respond with a JSON object with keys "scores" (mapping dimension names '
            f'to integer scores) and "rationale" (a brief explanation).'
        )

    def _parse_scores(
        self,
        llm_response: dict,
        dimensions: list[str],
        scale_min: int,
        scale_max: int,
    ) -> dict[str, int]:
        raw_scores = llm_response.get("scores", {})
        parsed: dict[str, int] = {}
        for dim in dimensions:
            score = raw_scores.get(dim, scale_min)
            if isinstance(score, (int, float)):
                score = int(max(scale_min, min(scale_max, score)))
            else:
                score = scale_min
            parsed[dim] = score
        return parsed

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "model": DEFAULT_MODEL,
                "temperature": DEFAULT_TEMPERATURE,
                "evaluation_dimensions": DEFAULT_DIMENSIONS,
                "scoring_scale": DEFAULT_SCORING_SCALE,
            },
            "inputs": {
                "concept_brief_set": {
                    "concepts": [
                        {
                            "id": "concept-1",
                            "name": "AI Health Coach",
                            "description": "A personalized AI health coaching app",
                        },
                        {
                            "id": "concept-2",
                            "name": "Smart Meal Planner",
                            "description": "An AI-powered meal planning service",
                        },
                    ],
                },
                "persona_set": {
                    "personas": [
                        {
                            "id": "persona-1",
                            "name": "Tech-Savvy Millennial",
                            "age": 30,
                            "interests": ["technology", "fitness"],
                        },
                        {
                            "id": "persona-2",
                            "name": "Busy Parent",
                            "age": 42,
                            "interests": ["family", "convenience"],
                        },
                    ],
                },
            },
            "expected_output": {
                "evaluation_set": {
                    "evaluations": [
                        {
                            "concept_id": "concept-1",
                            "persona_id": "persona-1",
                            "dimensions": {
                                "appeal": 5,
                                "uniqueness": 4,
                                "purchase_intent": 4,
                                "clarity": 5,
                            },
                            "rationale": "Tech-savvy users find AI health coaching highly appealing.",
                        },
                        {
                            "concept_id": "concept-1",
                            "persona_id": "persona-2",
                            "dimensions": {
                                "appeal": 3,
                                "uniqueness": 3,
                                "purchase_intent": 2,
                                "clarity": 4,
                            },
                            "rationale": "Busy parents may find it less relevant to their needs.",
                        },
                        {
                            "concept_id": "concept-2",
                            "persona_id": "persona-1",
                            "dimensions": {
                                "appeal": 3,
                                "uniqueness": 2,
                                "purchase_intent": 3,
                                "clarity": 4,
                            },
                            "rationale": "Millennials might find meal planning apps common.",
                        },
                        {
                            "concept_id": "concept-2",
                            "persona_id": "persona-2",
                            "dimensions": {
                                "appeal": 5,
                                "uniqueness": 3,
                                "purchase_intent": 5,
                                "clarity": 5,
                            },
                            "rationale": "Busy parents highly value automated meal planning.",
                        },
                    ],
                },
            },
        }
