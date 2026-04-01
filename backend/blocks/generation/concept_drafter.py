"""Concept Drafter block — LLM-powered concept brief generation from respondent data."""

from typing import Any

from blocks._llm_client import BlockExecutionError, call_llm_json
from blocks.base import GenerationBase


class ConceptDrafter(GenerationBase):
    """Generates product or creative concept briefs from respondent data using an LLM."""

    @property
    def input_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def output_schemas(self) -> list[str]:
        return ["concept_brief_set"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt_template": {
                    "type": "string",
                    "description": "Prompt template for concept generation. Use {input} as placeholder for respondent data.",
                },
                "n_concepts": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                    "description": "Number of concept briefs to generate",
                },
                "model": {
                    "type": "string",
                    "default": "claude-sonnet-4-6",
                    "description": "LLM model identifier",
                },
                "temperature": {
                    "type": "number",
                    "default": 0.7,
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Sampling temperature for creativity control",
                },
                "seed": {
                    "type": "integer",
                    "description": "Optional seed for reproducibility tracking",
                },
            },
            "required": ["prompt_template"],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return "Generates product or creative concept briefs from survey respondent data using a language model. Use this block when you need to ideate and articulate multiple concept variants based on customer needs, pain points, or preferences expressed in structured data. Concepts include name, description, and key differentiators."

    @property
    def methodological_notes(self) -> str:
        return "Non-deterministic LLM-powered generation — outputs vary with temperature, seed, and model version. Track these parameters for reproducibility. Quality depends heavily on prompt_template design — provide clear context about the product category, target audience, and innovation goals. The respondent_collection input should contain relevant attributes (needs, behaviors, frustrations) that inform concept development. Generated concepts are starting points for further refinement and evaluation downstream."

    @property
    def tags(self) -> list[str]:
        return [
            "llm",
            "generation",
            "concepts",
            "ideation",
            "product-development",
            "creative",
            "non-deterministic",
            "prompt-based",
        ]

    def validate_config(self, config: dict) -> bool:
        """Validate configuration against schema requirements."""
        # Check required field
        if not isinstance(config.get("prompt_template"), str):
            return False
        if not config["prompt_template"].strip():
            return False

        # Validate n_concepts if provided
        if "n_concepts" in config:
            n_concepts = config["n_concepts"]
            if not isinstance(n_concepts, int) or n_concepts < 1 or n_concepts > 20:
                return False

        # Validate temperature if provided
        if "temperature" in config:
            temp = config["temperature"]
            if not isinstance(temp, (int, float)) or temp < 0.0 or temp > 1.0:
                return False

        # Validate model if provided
        if "model" in config and (
            not isinstance(config["model"], str) or not config["model"].strip()
        ):
            return False

        # Validate seed if provided
        return not ("seed" in config and not isinstance(config["seed"], int))

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        """Generate concept briefs from respondent data using LLM."""
        # Extract respondent collection
        collection = inputs["respondent_collection"]
        rows = collection.get("rows", collection) if isinstance(collection, dict) else collection

        # Build prompts
        system_prompt = """You are an expert product developer and creative strategist. Your task is to generate product or creative concept briefs based on customer research data.

Each concept should include:
- name: A concise, memorable concept name
- description: A 2-3 sentence description of what the concept is and who it's for
- differentiators: 3-5 bullet points explaining what makes this concept unique or compelling

Respond only with valid JSON in this format:
{
  "concepts": [
    {
      "name": "Concept Name",
      "description": "Concept description...",
      "differentiators": ["point 1", "point 2", "point 3"]
    }
  ]
}"""

        user_prompt_template = config["prompt_template"]
        user_prompt = user_prompt_template.replace("{input}", str(rows))
        user_prompt = (
            f"{user_prompt}\n\nGenerate exactly {config.get('n_concepts', 5)} concept briefs."
        )

        # Call LLM with JSON response parsing
        try:
            response = await call_llm_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=config.get("model", "claude-sonnet-4-6"),
                temperature=config.get("temperature", 0.7),
                max_tokens=4096,
            )
        except BlockExecutionError as e:
            raise BlockExecutionError(f"Concept generation failed: {e}") from e

        # Validate response structure
        if "concepts" not in response:
            raise BlockExecutionError("LLM response missing 'concepts' key")

        concepts = response["concepts"]
        if not isinstance(concepts, list):
            raise BlockExecutionError("LLM response 'concepts' is not a list")

        # Validate each concept has required fields
        for i, concept in enumerate(concepts):
            if not isinstance(concept, dict):
                raise BlockExecutionError(f"Concept {i} is not a dict")
            required_fields = ["name", "description", "differentiators"]
            for field in required_fields:
                if field not in concept:
                    raise BlockExecutionError(f"Concept {i} missing required field: {field}")

        return {"concept_brief_set": {"concepts": concepts}}

    def test_fixtures(self) -> dict:
        """Provide test fixtures for contract testing."""
        return {
            "config": {
                "prompt_template": "Generate product concepts for home office furniture based on these customer needs: {input}",
                "n_concepts": 3,
                "model": "claude-sonnet-4-6",
                "temperature": 0.7,
                "seed": 42,
            },
            "inputs": {
                "respondent_collection": {
                    "rows": [
                        {
                            "respondent_id": "r1",
                            "pain_points": "Back pain from sitting too long, lack of storage, desk too small",
                            "needs": "Ergonomic support, ample workspace, organization solutions",
                        },
                        {
                            "respondent_id": "r2",
                            "pain_points": "Cluttered workspace, poor lighting, uncomfortable chair",
                            "needs": "Clean aesthetic, adjustable lighting, lumbar support",
                        },
                    ],
                },
            },
            "expected_output": {
                "concept_brief_set": {
                    "concepts": [
                        {
                            "name": "ErgoFlow Desk",
                            "description": "A height-adjustable desk with built-in cable management and ergonomic keyboard tray.",
                            "differentiators": [
                                "Electric height adjustment with memory presets",
                                "Integrated cable management system",
                                "Detachable ergonomic keyboard tray",
                            ],
                        },
                        {
                            "name": "LumbarLife Chair",
                            "description": "An office chair with adaptive lumbar support and breathable mesh back.",
                            "differentiators": [
                                "Automatic lumbar adjustment based on sitting position",
                                "Breathable mesh material for temperature regulation",
                                "12-hour battery-free operation",
                            ],
                        },
                        {
                            "name": "ClearView Organizer",
                            "description": "Modular desk organization system with integrated task lighting.",
                            "differentiators": [
                                "Magnetic modular components for customizable layouts",
                                "LED task lighting with color temperature adjustment",
                                "Hidden storage compartments for clutter-free workspace",
                            ],
                        },
                    ]
                }
            },
        }
