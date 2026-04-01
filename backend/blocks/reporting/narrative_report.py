"""Narrative Report block — LLM-powered narrative synthesis from multiple upstream outputs."""

from typing import Any

from blocks._llm_client import BlockExecutionError, call_llm
from blocks.base import ReportingBase


class NarrativeReport(ReportingBase):
    """LLM-powered narrative synthesis that combines evaluation results, source documents, and segment profiles into a coherent story."""

    @property
    def input_schemas(self) -> list[str]:
        return ["evaluation_set", "text_corpus", "segment_profile_set"]

    @property
    def output_schemas(self) -> list[str]:
        return ["text_corpus"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "narrative_style": {
                    "type": "string",
                    "enum": ["executive_summary", "detailed", "presentation_notes"],
                    "description": "Style and depth of the narrative report",
                },
                "audience": {
                    "type": "string",
                    "description": "Target audience for the report (e.g., 'executives', 'research team', 'stakeholders')",
                },
                "max_length": {
                    "type": "integer",
                    "default": 2000,
                    "minimum": 500,
                    "maximum": 10000,
                    "description": "Maximum length of the narrative in tokens",
                },
                "model": {
                    "type": "string",
                    "default": "claude-sonnet-4-6",
                    "description": "LLM model identifier",
                },
                "temperature": {
                    "type": "number",
                    "default": 0.5,
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Sampling temperature for narrative generation",
                },
                "seed": {
                    "type": "integer",
                    "description": "Optional seed for reproducibility tracking",
                },
            },
            "required": ["narrative_style"],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return "Synthesizes evaluation results, source documents, and segment profiles into a coherent narrative report using a language model. Use this block when you need to transform multiple analytical outputs into a human-readable story that explains findings, connects insights across data sources, and provides actionable recommendations for stakeholders."

    @property
    def methodological_notes(self) -> str:
        return "Non-deterministic LLM-powered synthesis — outputs vary with temperature, seed, and model version. Track these parameters for reproducibility. Quality depends on the richness and structure of input data: evaluation_set should contain scored assessments, text_corpus should provide source material for evidence, and segment_profile_set should describe customer segments with clear characteristics. The narrative_style parameter controls depth: executive_summary for high-level insights (1-2 paragraphs), detailed for comprehensive analysis (multiple sections with evidence), presentation_notes for bulleted talking points. Consider the audience parameter to tailor language and depth appropriately."

    @property
    def tags(self) -> list[str]:
        return [
            "llm",
            "reporting",
            "narrative",
            "synthesis",
            "multi-input",
            "non-deterministic",
            "storytelling",
            "insights",
        ]

    def declare_pipeline_inputs(self) -> list[str]:
        """List upstream node IDs whose outputs are needed for narrative synthesis."""
        return ["evaluation_set", "text_corpus", "segment_profile_set"]

    def validate_config(self, config: dict) -> bool:
        """Validate configuration against schema requirements."""
        # Check required field
        if not isinstance(config.get("narrative_style"), str):
            return False
        valid_styles = {"executive_summary", "detailed", "presentation_notes"}
        if config["narrative_style"] not in valid_styles:
            return False

        # Validate audience if provided
        if "audience" in config and (
            not isinstance(config["audience"], str) or not config["audience"].strip()
        ):
            return False

        # Validate max_length if provided
        if "max_length" in config:
            max_len = config["max_length"]
            if not isinstance(max_len, int) or max_len < 500 or max_len > 10000:
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
        """Generate narrative synthesis from multiple inputs using LLM."""
        # Extract inputs with fallback for missing data
        eval_data = inputs.get("evaluation_set", {})
        text_data = inputs.get("text_corpus", {})
        segment_data = inputs.get("segment_profile_set", {})

        # Normalize data structures
        evaluations = eval_data.get("evaluations", []) if isinstance(eval_data, dict) else []
        documents = text_data.get("documents", []) if isinstance(text_data, dict) else []
        segments = segment_data.get("segments", []) if isinstance(segment_data, dict) else []

        # Build system prompt based on narrative style
        style = config["narrative_style"]
        if style == "executive_summary":
            system_prompt = """You are an expert research analyst writing executive summaries. Your task is to synthesize evaluation results, source documents, and segment profiles into a concise 1-2 paragraph narrative that captures the most important insights and recommendations for busy executives.

Focus on:
- Key findings from the evaluation data
- Critical insights from segment profiles
- Actionable recommendations backed by evidence
- Clear, jargon-free language appropriate for senior leadership

Keep the summary brief (150-250 words), impactful, and forward-looking."""
        elif style == "detailed":
            system_prompt = """You are an expert research analyst writing comprehensive analytical reports. Your task is to synthesize evaluation results, source documents, and segment profiles into a detailed narrative that explains findings, connects insights across data sources, and provides evidence-based recommendations.

Structure your report with:
- Introduction: Brief context and objectives
- Key Findings: Main insights from evaluations and segments
- Evidence: Support from source documents
- Recommendations: Specific, actionable next steps
- Conclusion: Summary and implications

Use clear section headings, provide specific evidence from the data, and maintain a professional analytical tone."""
        else:  # presentation_notes
            system_prompt = """You are an expert research analyst preparing presentation talking points. Your task is to synthesize evaluation results, source documents, and segment profiles into bulleted notes that a presenter can use to communicate findings effectively.

Format your response as:
- Key Insights: 3-5 bullet points on main findings
- Segment Highlights: 2-3 bullets per important segment
- Recommendations: Actionable items in bullet form
- Supporting Evidence: Brief references to source material

Keep bullets concise (1-2 lines each), use active language, and focus on what the audience needs to know and remember."""

        # Build user prompt with data
        user_prompt_parts = ["Synthesize the following research data into a coherent narrative:\n"]

        # Add evaluation data
        if evaluations:
            user_prompt_parts.append("## Evaluation Results\n")
            for i, ev in enumerate(evaluations[:10]):  # Limit to prevent token overflow
                user_prompt_parts.append(f"{i + 1}. {ev}\n")

        # Add segment profiles
        if segments:
            user_prompt_parts.append("\n## Segment Profiles\n")
            for i, seg in enumerate(segments[:10]):  # Limit to prevent token overflow
                user_prompt_parts.append(f"{i + 1}. {seg}\n")

        # Add source documents
        if documents:
            user_prompt_parts.append("\n## Source Documents\n")
            for i, doc in enumerate(documents[:5]):  # Limit to prevent token overflow
                user_prompt_parts.append(f"Document {i + 1}: {doc[:500]}...\n")

        # Add audience context if provided
        if "audience" in config:
            user_prompt_parts.append(f"\nTarget Audience: {config['audience']}")

        user_prompt = "".join(user_prompt_parts)

        # Call LLM
        try:
            narrative = await call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=config.get("model", "claude-sonnet-4-6"),
                temperature=config.get("temperature", 0.5),
                max_tokens=config.get("max_length", 2000),
            )
        except BlockExecutionError as e:
            raise BlockExecutionError(f"Narrative generation failed: {e}") from e

        return {"text_corpus": {"documents": [narrative]}}

    def test_fixtures(self) -> dict:
        """Provide test fixtures for contract testing."""
        return {
            "config": {
                "narrative_style": "executive_summary",
                "audience": "executives",
                "max_length": 2000,
                "model": "claude-sonnet-4-6",
                "temperature": 0.5,
                "seed": 42,
            },
            "inputs": {
                "evaluation_set": {
                    "evaluations": [
                        {
                            "subject": "Concept A",
                            "criteria": ["appeal", "relevance", "uniqueness"],
                            "scores": {"appeal": 8, "relevance": 7, "uniqueness": 6},
                            "notes": "Strong appeal but moderate differentiation",
                        },
                        {
                            "subject": "Concept B",
                            "criteria": ["appeal", "relevance", "uniqueness"],
                            "scores": {"appeal": 7, "relevance": 9, "uniqueness": 8},
                            "notes": "Highly relevant to target needs",
                        },
                    ],
                },
                "text_corpus": {
                    "documents": [
                        "Customer feedback indicates strong demand for ergonomic solutions. 78% of respondents report back pain from current setups.",
                        "Price sensitivity varies by segment. Premium customers value quality over cost, while budget segment prioritizes affordability.",
                    ],
                },
                "segment_profile_set": {
                    "segments": [
                        {
                            "segment_id": "seg_1",
                            "name": "Premium Professionals",
                            "size": 35,
                            "characteristics": [
                                "High income",
                                "Quality-focused",
                                "Brand-conscious",
                            ],
                            "needs": ["Ergonomics", "Aesthetics", "Premium materials"],
                        },
                        {
                            "segment_id": "seg_2",
                            "name": "Budget Home Workers",
                            "size": 45,
                            "characteristics": ["Price-sensitive", "Practical", "Value-focused"],
                            "needs": ["Affordability", "Functionality", "Durability"],
                        },
                    ],
                },
            },
            "expected_output": {
                "text_corpus": {
                    "documents": [
                        "Executive Summary: Analysis reveals Concept B demonstrates stronger alignment with customer needs, particularly in relevance (9/10) and uniqueness (8/10) compared to Concept A. The premium professional segment (35% of market) prioritizes ergonomics and quality, while budget-focused home workers (45%) seek affordability without sacrificing functionality. Customer feedback indicates 78% experience back pain, validating the ergonomic focus. Recommendation: Advance Concept B to prototyping with emphasis on its strong relevance and differentiation, while exploring modular design options to address both premium and budget segment needs.",
                    ],
                },
            },
        }
