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
        return "Synchronization point that collects multiple evaluation_set inputs from parallel pipeline branches and produces a combined comparison output. Use this block when you need to wait for two or more independent evaluation branches to complete before aggregating, ranking, or diffing their results. Common use cases include comparing alternative concepts against the same criteria, evaluating different segment responses to the same stimulus, or aggregating multi-rater assessments where consistency or disagreement analysis is required."

    @property
    def methodological_notes(self) -> str:
        return "Assumes all incoming evaluation_set inputs are structurally comparable — they must evaluate against compatible criteria or score scales. The 'rank' mode assumes numeric scores can be ordered; the 'diff' mode assumes identical subject IDs across branches; the 'aggregate' mode simply concatenates all evaluations. Requires that expected_branches matches the actual number of incoming edges — mismatches will cause execution to hang or fail. For meaningful comparisons, ensure upstream evaluation blocks use consistent scoring schemes and criteria definitions. Alternative: use separate evaluation blocks and a custom reporting block if you need complex cross-tabulation or statistical comparison beyond simple aggregation."

    @property
    def tags(self) -> list[str]:
        return [
            "comparator",
            "sync",
            "parallel",
            "aggregation",
            "evaluation",
            "ranking",
            "multi-branch",
            "comparison",
        ]

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
