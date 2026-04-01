"""Stimulus Creator block — LLM-powered stimulus material generation from concept briefs."""

from typing import Any

from blocks._llm_client import BlockExecutionError, call_llm
from blocks.base import GenerationBase


class StimulusCreator(GenerationBase):
    """Generates research stimulus materials from concept briefs using an LLM."""

    @property
    def input_schemas(self) -> list[str]:
        return ["concept_brief_set"]

    @property
    def output_schemas(self) -> list[str]:
        return ["text_corpus"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "stimulus_type": {
                    "type": "string",
                    "enum": ["concept_board", "ad_copy", "product_description"],
                    "description": "Type of stimulus material to generate",
                },
                "tone": {
                    "type": "string",
                    "description": "Optional tone or style guidance for the stimulus materials",
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
            "required": ["stimulus_type"],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return "Generates research stimulus materials from concept briefs using a language model. Use this block to create concept boards, ad copy, or product descriptions from product or creative concept briefs. Each concept is transformed into a tailored stimulus material suitable for research testing, marketing campaigns, or product documentation. The optional tone parameter allows style customization (e.g., 'professional', 'playful', 'luxury')."

    @property
    def methodological_notes(self) -> str:
        return "Non-deterministic LLM-powered generation — outputs vary with temperature, seed, and model version. Track these parameters for reproducibility. The quality of stimulus materials depends on the richness of input concept briefs — concepts with clear descriptions and strong differentiators yield more compelling outputs. For concept_board: generates visual descriptions and imagery guidance. For ad_copy: produces headline and body copy variations. For product_description: creates detailed product narratives. The optional tone parameter guides stylistic approach across all generated materials."

    @property
    def tags(self) -> list[str]:
        return [
            "llm",
            "generation",
            "stimulus",
            "concept-boards",
            "ad-copy",
            "product-descriptions",
            "marketing",
            "creative",
            "non-deterministic",
            "concept-driven",
        ]

    def validate_config(self, config: dict) -> bool:
        """Validate configuration against schema requirements."""
        # Check required field
        if not isinstance(config.get("stimulus_type"), str):
            return False
        valid_types = {"concept_board", "ad_copy", "product_description"}
        if config["stimulus_type"] not in valid_types:
            return False

        # Validate tone if provided
        if "tone" in config and (not isinstance(config["tone"], str) or not config["tone"].strip()):
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
        """Generate stimulus materials from concept briefs using LLM."""
        # Extract concept briefs
        concept_data = inputs["concept_brief_set"]
        concepts = (
            concept_data.get("concepts", concept_data)
            if isinstance(concept_data, dict)
            else concept_data
        )

        if not isinstance(concepts, list):
            raise BlockExecutionError("concept_brief_set must contain a list of concepts")

        stimulus_type = config["stimulus_type"]
        tone = config.get("tone")

        # Get the appropriate prompt template
        system_prompt = self._get_system_prompt(stimulus_type, tone)

        # Build user prompt from concepts
        user_prompt = self._build_user_prompt(concepts, stimulus_type)

        # Call LLM for text response
        try:
            response_text = await call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=config.get("model", "claude-sonnet-4-6"),
                temperature=config.get("temperature", 0.7),
                max_tokens=6144,
            )
        except BlockExecutionError as e:
            raise BlockExecutionError(f"Stimulus generation failed: {e}") from e

        # Parse response into text corpus documents
        documents = self._parse_response_to_documents(response_text, concepts, stimulus_type)

        return {"text_corpus": {"documents": documents}}

    def _get_system_prompt(self, stimulus_type: str, tone: str | None) -> str:
        """Get the system prompt for the given stimulus type."""
        base_instruction = """You are an expert creative writer and marketing specialist. Your task is to transform product or creative concept briefs into compelling stimulus materials.

Generate one stimulus item per concept provided. Each stimulus should be detailed, engaging, and ready for use in research testing or marketing campaigns."""

        type_instructions = {
            "concept_board": """For CONCEPT BOARD format, each stimulus should include:
- A vivid visual description of the concept imagery
- Key visual elements and composition details
- Color palette and mood guidance
- Suggested layout or framing
- Emotional tone and atmosphere

Format each stimulus as a clearly labeled section with descriptive prose.""",
            "ad_copy": """For AD COPY format, each stimulus should include:
- A compelling headline (5-10 words, punchy and memorable)
- Subheadline or tagline if appropriate
- Body copy (2-3 paragraphs of persuasive text)
- Call to action
- Key messaging points highlighted

Format each stimulus as a clearly labeled section with marketing-ready copy.""",
            "product_description": """For PRODUCT DESCRIPTION format, each stimulus should include:
- Product name and positioning statement
- Detailed feature descriptions (3-5 paragraphs)
- Benefit elaborations connecting features to user needs
- Use case scenarios
- Technical specifications if relevant

Format each stimulus as a clearly labeled section with comprehensive product narrative.""",
        }

        prompt = f"{base_instruction}\n\n{type_instructions[stimulus_type]}"

        if tone:
            prompt += f"\n\nTone guidance: Use a {tone} tone throughout all stimulus materials."

        return prompt

    def _build_user_prompt(self, concepts: list, stimulus_type: str) -> str:
        """Build the user prompt from concept briefs."""
        prompt_parts = [
            f"Generate {stimulus_type.replace('_', ' ')} materials for the following {len(concepts)} concepts:\n"
        ]

        for i, concept in enumerate(concepts, 1):
            if not isinstance(concept, dict):
                continue

            prompt_parts.append(f"\nConcept {i}:")
            if "name" in concept:
                prompt_parts.append(f"  Name: {concept['name']}")
            if "description" in concept:
                prompt_parts.append(f"  Description: {concept['description']}")
            if "differentiators" in concept:
                diff = concept["differentiators"]
                if isinstance(diff, list):
                    prompt_parts.append("  Differentiators:")
                    for d in diff:
                        prompt_parts.append(f"    - {d}")
                else:
                    prompt_parts.append(f"  Differentiators: {diff}")

        prompt_parts.append(
            "\n\nGenerate one stimulus item per concept, following the format specified in the system prompt."
        )

        return "\n".join(prompt_parts)

    def _parse_response_to_documents(
        self, response_text: str, concepts: list, stimulus_type: str
    ) -> list[str]:
        """Parse LLM response into text corpus documents.

        The response is expected to contain one stimulus per concept.
        We split by common delimiters and validate the count.
        """
        # Try to split by common section delimiters
        documents = []

        # Common patterns for section breaks
        possible_splits = [
            "\n\nConcept ",
            "\n\nSTIMULUS ",
            "\n\n---",
            "\n\n##",
            "\n\n#",
        ]

        # First, try to split by delimiters
        for delimiter in possible_splits:
            if delimiter in response_text:
                raw_sections = response_text.split(delimiter)
                # First section might be intro text, skip if it doesn't look like content
                if len(raw_sections) > 1:
                    sections = [s.strip() for s in raw_sections[1:] if s.strip()]
                    if len(sections) == len(concepts):
                        documents = sections
                        break

        # If no clean split found, try paragraph blocks
        if not documents:
            paragraphs = [p.strip() for p in response_text.split("\n\n") if p.strip()]
            # Group paragraphs into documents (approx 2-4 paragraphs per concept)
            paragraphs_per_concept = max(1, len(paragraphs) // len(concepts))
            for i in range(len(concepts)):
                start_idx = i * paragraphs_per_concept
                end_idx = (
                    start_idx + paragraphs_per_concept if i < len(concepts) - 1 else len(paragraphs)
                )
                doc = "\n\n".join(paragraphs[start_idx:end_idx])
                if doc:
                    documents.append(doc)

        # Fallback: if we still don't have enough documents, split by single paragraphs
        if len(documents) < len(concepts):
            single_paragraphs = [p.strip() for p in response_text.split("\n") if p.strip()]
            documents = []
            for i in range(len(concepts)):
                idx = min(i, len(single_paragraphs) - 1)
                if idx < len(single_paragraphs):
                    documents.append(single_paragraphs[idx])

        # Ensure we have at least one document per concept
        while len(documents) < len(concepts):
            documents.append(f"Stimulus content for concept {len(documents) + 1}")

        # Trim excess if LLM generated too many
        documents = documents[: len(concepts)]

        return documents

    def test_fixtures(self) -> dict:
        """Provide test fixtures for contract testing."""
        return {
            "config": {
                "stimulus_type": "product_description",
                "tone": "professional",
                "model": "claude-sonnet-4-6",
                "temperature": 0.7,
                "seed": 42,
            },
            "inputs": {
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
                    ]
                }
            },
            "expected_output": {
                "text_corpus": {
                    "documents": [
                        "ErgoFlow Desk - Professional Height-Adjustable Workstation\n\nThe ErgoFlow Desk represents the pinnacle of modern workspace ergonomics, combining cutting-edge technology with thoughtful design. This height-adjustable desk features electric lift mechanism with customizable memory presets, allowing seamless transitions between sitting and standing positions throughout your workday.\n\nKey Features:\n- Electric height adjustment with smooth, quiet operation\n- Programmable memory presets for your preferred heights\n- Integrated cable management system keeps your workspace clean and organized\n- Detachable ergonomic keyboard tray for optimal typing position\n- Premium construction with sustainable materials\n\nIdeal for professionals seeking enhanced comfort and productivity, the ErgoFlow Desk adapts to your workflow, not the other way around.",
                        "LumbarLife Chair - Adaptive Seating Solutions\n\nExperience unparalleled comfort with the LumbarLife Chair, featuring revolutionary adaptive lumbar support technology. This intelligent chair automatically adjusts to your sitting position, providing customized lower back support that responds to your movements in real-time.\n\nKey Features:\n- Automatic lumbar adjustment with position-sensing technology\n- Breathable mesh back promotes airflow and temperature regulation\n- 12-hour battery-free operation for all-day comfort\n- Ergonomic design certified by workplace health experts\n- Durable construction with eco-friendly materials\n\nThe LumbarLife Chair is designed for professionals who demand superior comfort and support during extended work sessions. Say goodbye to back pain and hello to productive, pain-free workdays.",
                    ]
                }
            },
        }
