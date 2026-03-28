"""Side-by-side Comparator block — compares multiple same-type inputs."""

from typing import Any

from blocks.base import ComparatorBase


class SideBySideComparator(ComparatorBase):
    """Sync point that waits for parallel branches and produces a comparison."""

    @property
    def input_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def output_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["rank", "diff", "aggregate"],
                    "default": "aggregate",
                    "description": "Comparison strategy",
                },
                "expected_branches": {
                    "type": "integer",
                    "minimum": 2,
                    "description": "Number of parallel inputs to expect",
                },
            },
            "required": ["expected_branches"],
        }

    @property
    def description(self) -> str:
        return "Compares multiple evaluation_set inputs from parallel branches and produces a combined comparison."

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config.get("expected_branches"), int):
            return False
        if config["expected_branches"] < 2:
            return False
        valid_modes = {"rank", "diff", "aggregate"}
        return config.get("mode", "aggregate") in valid_modes

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        mode = config.get("mode", "aggregate")
        # inputs["evaluation_set"] is a list of evaluation_sets from parallel branches
        eval_sets = inputs["evaluation_set"]
        if not isinstance(eval_sets, list):
            eval_sets = [eval_sets]

        all_evaluations = []
        for eval_set in eval_sets:
            evs = eval_set.get("evaluations", eval_set) if isinstance(eval_set, dict) else eval_set
            all_evaluations.extend(evs)

        comparison = {
            "mode": mode,
            "branch_count": len(eval_sets),
            "evaluations": all_evaluations,
        }

        return {"evaluation_set": {"evaluations": [comparison]}}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "mode": "aggregate",
                "expected_branches": 2,
            },
            "inputs": {
                "evaluation_set": [
                    {"evaluations": [{"subject": "A", "scores": {"clarity": 4}}]},
                    {"evaluations": [{"subject": "B", "scores": {"clarity": 5}}]},
                ],
            },
            "expected_output": {
                "evaluation_set": {
                    "evaluations": [
                        {
                            "mode": "aggregate",
                            "branch_count": 2,
                            "evaluations": [
                                {"subject": "A", "scores": {"clarity": 4}},
                                {"subject": "B", "scores": {"clarity": 5}},
                            ],
                        },
                    ],
                },
            },
        }
