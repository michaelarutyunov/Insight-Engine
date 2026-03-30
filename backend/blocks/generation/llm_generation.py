"""LLM Generation block — generates text content from input data using an LLM."""

from typing import Any

from blocks.base import GenerationBase


class LLMGeneration(GenerationBase):
    """Non-deterministic block that produces text_corpus from input data via an LLM call."""

    @property
    def input_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def output_schemas(self) -> list[str]:
        return ["text_corpus"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt_template": {
                    "type": "string",
                    "description": "Prompt template with {input} placeholder for the input data",
                },
                "model": {
                    "type": "string",
                    "default": "claude-sonnet-4-20250514",
                    "description": "LLM model identifier",
                },
                "seed": {
                    "type": "integer",
                    "description": "Optional seed for reproducibility tracking",
                },
            },
            "required": ["prompt_template"],
        }

    @property
    def description(self) -> str:
        return "Generates qualitative text content (concepts, narratives, themes) from structured respondent data using a language model prompt template. Use this block when you need LLM-powered synthesis, creative ideation, or open-ended interpretation that requires semantic understanding beyond deterministic transformation rules."

    @property
    def methodological_notes(self) -> str:
        return "Assumes availability of configured LLM API and prompt engineering expertise. Non-deterministic by design — outputs vary with temperature, seed, and model version; track these parameters for reproducibility. Token limits may constrain input size or truncate outputs; consider chunking large respondent collections. Quality depends heavily on prompt template design — include clear instructions, examples, and output format specifications. Deterministic transform blocks are preferable for structured calculations or rule-based processing."

    @property
    def tags(self) -> list[str]:
        return [
            "llm",
            "generation",
            "text",
            "qualitative",
            "prompt-based",
            "non-deterministic",
            "concepts",
            "narratives",
        ]

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config.get("prompt_template"), str):
            return False
        if not config["prompt_template"].strip():
            return False
        return "seed" not in config or isinstance(config["seed"], int)

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        # In production, this would call an LLM API.
        # For now, we render the prompt and return a placeholder response.
        collection = inputs["respondent_collection"]
        rows = collection.get("rows", collection) if isinstance(collection, dict) else collection
        rendered = config["prompt_template"].replace("{input}", str(rows))
        # Placeholder: return the rendered prompt as the generated document
        return {"text_corpus": {"documents": [rendered]}}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "prompt_template": "Summarize these respondents: {input}",
                "model": "claude-sonnet-4-20250514",
                "seed": 42,
            },
            "inputs": {
                "respondent_collection": {
                    "rows": [{"name": "Alice", "age": "30"}],
                },
            },
            "expected_output": {
                "text_corpus": {
                    "documents": ["Summarize these respondents: [{'name': 'Alice', 'age': '30'}]"],
                },
            },
        }
