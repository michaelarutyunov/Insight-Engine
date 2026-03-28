"""Prompt Flex block — user-defined LLM prompt with configurable I/O shapes."""

from typing import Any

from blocks.base import LLMFlexBase


class PromptFlex(LLMFlexBase):
    """Flexible LLM block with user-defined prompt and configurable input/output types."""

    @property
    def input_schemas(self) -> list[str]:
        return ["text_corpus"]

    @property
    def output_schemas(self) -> list[str]:
        return ["text_corpus"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "system_prompt": {
                    "type": "string",
                    "description": "System-level instruction for the LLM",
                },
                "user_prompt_template": {
                    "type": "string",
                    "description": "User prompt template with {input} placeholder",
                },
                "output_format": {
                    "type": "string",
                    "enum": ["text", "json", "bullet_list"],
                    "default": "text",
                    "description": "Expected output format",
                },
            },
            "required": ["user_prompt_template"],
        }

    @property
    def description(self) -> str:
        return "User-configurable LLM prompt block that transforms text_corpus input into text_corpus output."

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config.get("user_prompt_template"), str):
            return False
        if not config["user_prompt_template"].strip():
            return False
        valid_formats = {"text", "json", "bullet_list"}
        return config.get("output_format", "text") in valid_formats

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        corpus = inputs["text_corpus"]
        documents = corpus.get("documents", corpus) if isinstance(corpus, dict) else corpus
        rendered = config["user_prompt_template"].replace("{input}", str(documents))
        # Placeholder: return rendered prompt as output document
        return {"text_corpus": {"documents": [rendered]}}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "system_prompt": "You are a research analyst.",
                "user_prompt_template": "Extract key themes from: {input}",
                "output_format": "bullet_list",
            },
            "inputs": {
                "text_corpus": {"documents": ["AI is transforming healthcare."]},
            },
            "expected_output": {
                "text_corpus": {
                    "documents": ["Extract key themes from: ['AI is transforming healthcare.']"],
                },
            },
        }
