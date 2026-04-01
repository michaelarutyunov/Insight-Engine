"""Presentation Outline block — LLM-powered presentation outline generation."""

from typing import Any

from blocks._llm_client import call_llm
from blocks.base import ReportingBase


class PresentationOutline(ReportingBase):
    """Generates structured presentation outlines from evaluation_set and text_corpus inputs using an LLM."""

    @property
    def input_schemas(self) -> list[str]:
        return ["evaluation_set", "text_corpus"]

    @property
    def output_schemas(self) -> list[str]:
        return ["text_corpus"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "n_slides": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                    "description": "Number of slides to generate in the outline",
                },
                "format": {
                    "type": "string",
                    "enum": ["bullet", "narrative"],
                    "default": "bullet",
                    "description": "Outline format: bullet (concise points) or narrative (detailed descriptions)",
                },
                "audience": {
                    "type": "string",
                    "description": "Target audience for the presentation (e.g., 'executives', 'researchers', 'general')",
                },
                "model": {
                    "type": "string",
                    "default": "claude-sonnet-4-20250514",
                    "description": "LLM model identifier for outline generation",
                },
                "temperature": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.5,
                    "description": "Sampling temperature for LLM generation",
                },
            },
            "required": [],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return "Generates structured presentation outlines from evaluation results and supporting documents using a language model. Use this block when you need to transform research findings into presentation-ready slide structures with clear narrative flow. The block synthesizes evaluation data with source context to create audience-appropriate outlines."

    @property
    def methodological_notes(self) -> str:
        return (
            "Assumes evaluation_set contains scored assessments and text_corpus provides supporting source material. "
            "The LLM synthesizes these inputs into a coherent presentation structure. Quality depends on input "
            "data completeness—missing or sparse evaluations may result in generic outlines. The 'audience' parameter "
            "helps tailor content depth and terminology; omit for general audiences. Higher temperature values (>0.7) "
            "produce more creative structures but may reduce factual grounding. For critical presentations, consider "
            "reviewing and editing the generated outline before final delivery. Token limits may truncate very long "
            "source documents; prioritize key documents in text_corpus input."
        )

    @property
    def tags(self) -> list[str]:
        return [
            "reporting",
            "llm",
            "presentation",
            "outline",
            "evaluation-summary",
            "multi-input",
            "non-deterministic",
        ]

    def declare_pipeline_inputs(self) -> list[str]:
        return ["evaluation_set", "text_corpus"]

    def validate_config(self, config: dict) -> bool:
        # n_slides validation
        n_slides = config.get("n_slides", 10)
        if not isinstance(n_slides, int) or n_slides < 1 or n_slides > 50:
            return False

        # format validation
        format_val = config.get("format", "bullet")
        if format_val not in ("bullet", "narrative"):
            return False

        # audience validation (optional)
        audience = config.get("audience")
        if audience is not None and not isinstance(audience, str):
            return False

        # model validation (optional)
        model = config.get("model", "claude-sonnet-4-20250514")
        if not isinstance(model, str) or not model.strip():
            return False

        # temperature validation
        temp = config.get("temperature", 0.5)
        return isinstance(temp, (int, float)) and 0.0 <= temp <= 1.0

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        # Extract config with defaults
        n_slides = config.get("n_slides", 10)
        format_val = config.get("format", "bullet")
        audience = config.get("audience", "general")
        model = config.get("model", "claude-sonnet-4-20250514")
        temperature = config.get("temperature", 0.5)

        # Extract input data
        eval_data = inputs.get("evaluation_set", {})
        text_data = inputs.get("text_corpus", {})

        evaluations = eval_data.get("evaluations", []) if isinstance(eval_data, dict) else []
        documents = text_data.get("documents", []) if isinstance(text_data, dict) else []

        # Build system prompt
        system_prompt = (
            "You are an expert presentation designer. Your task is to create a structured, "
            "audience-appropriate presentation outline based on evaluation results and supporting documents. "
            "The outline should have a clear narrative flow with a beginning, middle, and end."
        )

        # Build user prompt
        user_prompt = f"""Create a presentation outline with {n_slides} slides.

Format: {format_val}
Target Audience: {audience}

EVALUATION DATA:
{self._format_evaluations(evaluations)}

SUPPORTING DOCUMENTS:
{self._format_documents(documents)}

REQUIREMENTS:
1. Create exactly {n_slides} slides
2. Include a title slide and a closing/conclusion slide
3. Structure the middle slides to tell a coherent story
4. Use the evaluation data as the primary evidence
5. Reference supporting documents where relevant
6. Tailor the depth and terminology for the target audience

Output format:
"""
        if format_val == "bullet":
            user_prompt += """
Slide 1: [Title]
- Point 1
- Point 2

Slide 2: [Title]
- Point 1
- Point 2
...
"""
        else:  # narrative
            user_prompt += """
Slide 1: [Title]
Detailed description of slide content and speaker notes...

Slide 2: [Title]
Detailed description of slide content and speaker notes...
...
"""

        # Call LLM
        outline_text = await call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=4096,
        )

        return {"text_corpus": {"documents": [outline_text]}}

    def _format_evaluations(self, evaluations: list) -> str:
        """Format evaluations for the prompt."""
        if not evaluations:
            return "No evaluation data provided."
        lines = []
        for i, ev in enumerate(evaluations, 1):
            if isinstance(ev, dict):
                lines.append(f"Evaluation {i}: {ev}")
            else:
                lines.append(f"Evaluation {i}: {str(ev)}")
        return "\n".join(lines)

    def _format_documents(self, documents: list) -> str:
        """Format documents for the prompt."""
        if not documents:
            return "No supporting documents provided."
        lines = []
        for i, doc in enumerate(documents, 1):
            # Truncate very long documents to avoid token limits
            doc_str = str(doc)[:500]
            if len(str(doc)) > 500:
                doc_str += "... (truncated)"
            lines.append(f"Document {i}: {doc_str}")
        return "\n".join(lines)

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "n_slides": 5,
                "format": "bullet",
                "audience": "executives",
                "model": "claude-sonnet-4-20250514",
                "temperature": 0.5,
            },
            "inputs": {
                "evaluation_set": {
                    "evaluations": [
                        {"subject": "Product A", "scores": {"quality": 8, "value": 7}},
                        {"subject": "Product B", "scores": {"quality": 6, "value": 9}},
                    ],
                },
                "text_corpus": {
                    "documents": [
                        "Market research shows increasing demand for quality products.",
                        "Customer survey indicates price sensitivity is moderate.",
                    ]
                },
            },
            "expected_output": {
                "text_corpus": {
                    "documents": [
                        "Slide 1: Market Research Findings\n"
                        "- Overview of product evaluation results\n"
                        "- Key insights from customer survey\n\n"
                        "Slide 2: Product Comparison\n"
                        "- Product A: High quality, moderate value\n"
                        "- Product B: Moderate quality, high value\n\n"
                        "Slide 3: Quality Analysis\n"
                        "- Product A leads with score of 8\n"
                        "- Customer preference for quality features\n\n"
                        "Slide 4: Value Proposition\n"
                        "- Product B offers better value (score: 9)\n"
                        "- Price sensitivity considerations\n\n"
                        "Slide 5: Recommendations\n"
                        "- Consider hybrid approach combining strengths\n"
                        "- Further research on customer segments\n"
                    ]
                }
            },
        }
