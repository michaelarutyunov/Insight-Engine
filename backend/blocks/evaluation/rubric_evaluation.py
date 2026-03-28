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
        return "Evaluates text_corpus subjects against concept_brief criteria to produce scored assessments."

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
