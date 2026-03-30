"""Markdown Report block - assembles multiple upstream outputs into a formatted Markdown document."""

from typing import Any

from blocks.base import ReportingBase


class MarkdownReport(ReportingBase):
    """Assembles evaluation_set and text_corpus inputs into a structured Markdown report."""

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
                "title": {
                    "type": "string",
                    "description": "Report title",
                },
                "sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered list of section headings",
                },
            },
            "required": ["title"],
        }

    @property
    def description(self) -> str:
        return "If you need to compile evaluation results and source documents into a human-readable Markdown report for stakeholders, this is the right block. Use it when you want to present analysis findings with structured sections, clear headings, and proper document formatting."

    @property
    def methodological_notes(self) -> str:
        return (
            "Assumes that evaluation_set contains structured evaluation results with scores and that "
            "text_corpus provides source documents for citation. Requires properly formatted input data; "
            "malformed or missing evaluation data will result in incomplete reports. The block performs "
            "basic assembly without advanced formatting or template logic—for complex styling needs, "
            "consider custom reporting blocks. Report structure follows standard Markdown conventions with "
            "H1 (title), H2 (sections), and bullet lists for content."
        )

    @property
    def tags(self) -> list[str]:
        return ["reporting", "document-generation", "markdown", "evaluation-summary", "multi-input"]

    def declare_pipeline_inputs(self) -> list[str]:
        return ["evaluation_set", "text_corpus"]

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config.get("title"), str):
            return False
        return bool(config["title"].strip())

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        title = config["title"]
        sections = config.get("sections", [])
        parts: list[str] = []

        # Title
        parts.append(f"# {title}\n")

        # Evaluations section
        eval_data = inputs.get("evaluation_set", {})
        parts.append("## Evaluations\n")
        if eval_data:
            for ev in eval_data.get("evaluations", []):
                parts.append(f"- {ev}\n")

        # Source documents section
        text_data = inputs.get("text_corpus", {})
        parts.append("\n## Source Documents\n")
        if text_data:
            for doc in text_data.get("documents", []):
                parts.append(f"- {doc}\n")

        # Custom sections
        for section in sections:
            parts.append(f"\n## {section}\n")
            parts.append("*Section to be populated.*\n")

        # Default closing sections if no custom ones
        if not sections:
            parts.append("\n## Recommendations\n")
            parts.append("*Section to be populated.*\n")
            parts.append("\n## Appendix\n")
            parts.append("*Section to be populated.*\n")

        report = "".join(parts)
        return {"text_corpus": {"documents": [report]}}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "title": "Research Findings",
            },
            "inputs": {
                "evaluation_set": {
                    "evaluations": [
                        {"subject": "Doc A", "scores": {"clarity": 4}},
                    ],
                },
                "text_corpus": {"documents": ["AI trends document"]},
            },
            "expected_output": {
                "text_corpus": {
                    "documents": [
                        "# Research Findings\n"
                        "## Evaluations\n"
                        "- {'subject': 'Doc A', 'scores': {'clarity': 4}}\n"
                        "\n## Source Documents\n"
                        "- AI trends document\n"
                        "\n## Recommendations\n"
                        "*Section to be populated.*\n"
                        "\n## Appendix\n"
                        "*Section to be populated.*\n",
                    ],
                },
            },
        }
