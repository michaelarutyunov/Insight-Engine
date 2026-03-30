"""Rubric Evaluation block — scores subjects against defined criteria."""

from typing import Any

from blocks.base import EvaluationBase


class RubricEvaluation(EvaluationBase):
    """Judges subject data against evaluation criteria to produce scored assessments."""

    @property
    def input_schemas(self) -> list[str]:
        return ["text_corpus", "concept_brief_set"]

    @property
    def output_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "scoring_mode": {
                    "type": "string",
                    "enum": ["binary", "scale_5", "scale_10"],
                    "default": "scale_5",
                    "description": "Scoring scale to apply",
                },
                "criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of criteria names to evaluate against",
                },
            },
            "required": ["criteria"],
        }

    @property
    def description(self) -> str:
        return (
            "Scores text documents against a predefined rubric of evaluation criteria. "
            "Use when you need to assess subjects against consistent, structured standards "
            "with numeric scoring. Supports binary pass/fail, 5-point, or 10-point scales."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "ASSUMPTIONS: Rubric criteria are predefined and consistently applied across all subjects. "
            "Scoring scales are ordinal—intervals between scores may not be equal in meaning. "
            "The current implementation assigns placeholder scores; production use requires LLM integration "
            "or domain-specific scoring logic to meaningfully evaluate subjects against criteria.\n\n"
            "DATA REQUIREMENTS: text_corpus input with 'documents' key (list of text strings) or "
            "concept_brief_set with criteria definitions. Criteria names must match evaluation dimensions "
            "you intend to score. For meaningful evaluation, documents should contain sufficient content "
            "to assess against each criterion.\n\n"
            "LIMITATIONS: Placeholder scoring assigns maximum scores to all criteria; this is not "
            "meaningful evaluation. The block does not handle ambiguous or partial criterion matching— "
            "each criterion receives a single score. For qualitative feedback or rationale, consider "
            "LLM-powered evaluation blocks (e.g., ConceptEvaluation). Alternatives: use LLM Flex blocks "
            "for custom prompt-based evaluation, or ConceptEvaluation for persona-based concept assessment."
        )

    @property
    def tags(self) -> list[str]:
        return [
            "evaluation",
            "rubric-scoring",
            "structured-assessment",
            "numeric-scores",
            "text-corpus-input",
            "concept-brief-input",
            "criteria-based",
            "scoring-scales",
            "multi-criteria",
        ]

    def validate_config(self, config: dict) -> bool:
        if "criteria" not in config or not isinstance(config["criteria"], list):
            return False
        if not all(isinstance(c, str) for c in config.get("criteria", [])):
            return False
        if len(config.get("criteria", [])) == 0:
            return False
        valid_modes = {"binary", "scale_5", "scale_10"}
        return config.get("scoring_mode", "scale_5") in valid_modes

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        subjects = inputs["text_corpus"]
        documents = subjects.get("documents", subjects) if isinstance(subjects, dict) else subjects
        criteria_list = config["criteria"]
        scoring_mode = config.get("scoring_mode", "scale_5")

        # In production this would call an LLM to score.
        # Placeholder: assign a default score to each subject per criterion.
        max_scores = {"binary": 1, "scale_5": 5, "scale_10": 10}
        max_score = max_scores[scoring_mode]

        evaluations = []
        for doc in documents:
            scores = {criterion: max_score for criterion in criteria_list}
            evaluations.append(
                {
                    "subject": doc,
                    "scores": scores,
                    "scoring_mode": scoring_mode,
                }
            )

        return {"evaluation_set": {"evaluations": evaluations}}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "criteria": ["clarity", "relevance", "novelty"],
                "scoring_mode": "scale_5",
            },
            "inputs": {
                "text_corpus": {"documents": ["Doc about AI trends"]},
                "concept_brief_set": {
                    "concepts": [{"name": "AI innovation framework"}],
                },
            },
            "expected_output": {
                "evaluation_set": {
                    "evaluations": [
                        {
                            "subject": "Doc about AI trends",
                            "scores": {"clarity": 5, "relevance": 5, "novelty": 5},
                            "scoring_mode": "scale_5",
                        },
                    ],
                },
            },
        }
