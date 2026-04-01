"""PDF Report block - converts evaluation_set and text_corpus to PDF using weasyprint."""

import base64
from typing import Any

import markdown
from weasyprint import CSS, HTML

from blocks.base import ReportingBase


class PdfReport(ReportingBase):
    """Converts evaluation_set and text_corpus to formatted PDF document via weasyprint."""

    @property
    def input_schemas(self) -> list[str]:
        return ["evaluation_set", "text_corpus"]

    @property
    def output_schemas(self) -> list[str]:
        return ["generic_blob"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "output_format": {
                    "type": "string",
                    "enum": ["pdf"],
                    "description": "Output format (only PDF supported)",
                },
                "title": {
                    "type": "string",
                    "description": "Document title for PDF metadata",
                },
                "page_size": {
                    "type": "string",
                    "enum": ["A4", "Letter"],
                    "default": "A4",
                    "description": "PDF page size",
                },
                "sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of sections to include in order (e.g., ['executive_summary', 'evaluations', 'findings'])",
                },
                "include_charts": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to include chart visualizations in the PDF",
                },
                "pipeline_input_nodes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of upstream node IDs whose outputs to include (defaults to adjacent inputs only)",
                },
            },
            "required": ["output_format", "title"],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return (
            "Converts evaluation_set and text_corpus to a professionally formatted PDF document using weasyprint. "
            "Use this block when you need to deliver research findings, evaluation results, and analysis in PDF format. "
            "Supports configurable sections, optional chart visualizations, and flexible page sizes."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "Accepts evaluation_set containing scored assessments and text_corpus containing markdown-formatted documents. "
            "Converts markdown to HTML using the markdown library, then renders to PDF via weasyprint. "
            "The sections parameter controls report structure; when not provided, all available content is included in default order. "
            "include_charts adds placeholder visualizations for evaluation data (actual chart rendering requires additional dependencies). "
            "Assumes well-formed markdown; complex tables or advanced markdown extensions may not render perfectly. "
            "The output is PDF bytes encoded as base64 in the generic_blob data field."
        )

    @property
    def tags(self) -> list[str]:
        return ["reporting", "pdf", "document-generation", "markdown", "weasyprint", "evaluation"]

    def declare_pipeline_inputs(self) -> list[str]:
        """List upstream node IDs whose outputs are needed for PDF generation."""
        # This will be overridden by config["pipeline_input_nodes"] if provided
        # The engine will use this to collect inputs from non-adjacent nodes
        return []

    def validate_config(self, config: dict) -> bool:
        # Check required fields
        if "output_format" not in config:
            return False
        if config["output_format"] != "pdf":
            return False
        if "title" not in config:
            return False
        if not isinstance(config["title"], str) or not config["title"].strip():
            return False

        # Validate optional fields if present
        if "page_size" in config and config["page_size"] not in ["A4", "Letter"]:
            return False
        if "sections" in config:
            sections = config["sections"]
            if not isinstance(sections, list) or not all(isinstance(s, str) for s in sections):
                return False
        if "include_charts" in config and not isinstance(config["include_charts"], bool):
            return False
        if "pipeline_input_nodes" in config:
            nodes = config["pipeline_input_nodes"]
            if not isinstance(nodes, list) or not all(isinstance(n, str) for n in nodes):
                return False

        return True

    def _render_evaluation_table(self, evaluations: list[dict]) -> str:
        """Render evaluations as markdown table."""
        if not evaluations:
            return ""

        # Build markdown table
        lines = ["## Evaluation Results\n"]
        lines.append("| Subject | Criteria | Score | Notes |")
        lines.append("|--------|----------|-------|-------|")

        for eval_item in evaluations:
            subject = eval_item.get("subject", "N/A")
            criteria = eval_item.get("criteria", [])
            scores = eval_item.get("scores", {})
            notes = eval_item.get("notes", "")

            # Format criteria and scores
            if isinstance(criteria, list) and criteria:
                criteria_str = ", ".join(str(c) for c in criteria[:3])  # Limit to 3
                if len(criteria) > 3:
                    criteria_str += "..."
            else:
                criteria_str = str(criteria)

            if isinstance(scores, dict):
                score_values = list(scores.values())
                if score_values:
                    avg_score = sum(score_values) / len(score_values)
                    scores_str = f"{avg_score:.1f}"
                else:
                    scores_str = "N/A"
            else:
                scores_str = str(scores)

            lines.append(f"| {subject} | {criteria_str} | {scores_str} | {notes} |")

        return "\n".join(lines)

    def _render_charts_placeholder(self, evaluations: list[dict]) -> str:
        """Render placeholder for charts."""
        return """

---

## Charts

*Chart visualizations would be rendered here when include_charts is enabled.*

To enable actual chart generation, ensure matplotlib and other visualization dependencies are installed.

---

"""

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        # Extract configuration
        title = config["title"]
        page_size = config.get("page_size", "A4")
        sections = config.get("sections")
        include_charts = config.get("include_charts", False)

        # Extract inputs
        eval_data = inputs.get("evaluation_set", {})
        text_data = inputs.get("text_corpus", {})

        # Normalize data structures
        evaluations = eval_data.get("evaluations", []) if isinstance(eval_data, dict) else []
        documents = text_data.get("documents", []) if isinstance(text_data, dict) else []

        # Build markdown content
        markdown_parts = [f"# {title}\n"]

        # Determine section order
        default_sections = ["executive_summary", "evaluations", "findings", "appendix"]
        section_order = sections if sections else default_sections

        # Add executive summary from first document if available
        if "executive_summary" in section_order and documents:
            markdown_parts.append("## Executive Summary\n")
            markdown_parts.append(documents[0])
            markdown_parts.append("\n\n")

        # Add evaluation results
        if "evaluations" in section_order and evaluations:
            markdown_parts.append(self._render_evaluation_table(evaluations))
            markdown_parts.append("\n\n")

        # Add charts placeholder if enabled
        if include_charts and evaluations:
            markdown_parts.append(self._render_charts_placeholder(evaluations))

        # Add remaining documents as findings/analysis
        if "findings" in section_order and len(documents) > 1:
            markdown_parts.append("## Detailed Findings\n")
            for doc in documents[1:]:
                markdown_parts.append(doc)
                markdown_parts.append("\n\n---\n\n")

        # Combine all parts
        markdown_content = "\n".join(markdown_parts)

        # Convert markdown to HTML
        html_body = markdown.markdown(
            markdown_content, extensions=["tables", "fenced_code", "sane_lists", "toc"]
        )

        # Wrap in complete HTML document
        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 2em;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 1.5em;
            margin-bottom: 0.5em;
            font-weight: 600;
            line-height: 1.2;
        }}
        h1 {{ font-size: 2.5em; border-bottom: 2px solid #eee; padding-bottom: 0.3em; }}
        h2 {{ font-size: 2em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
        h3 {{ font-size: 1.5em; }}
        h4 {{ font-size: 1.25em; }}
        p {{ margin: 1em 0; }}
        ul, ol {{ margin: 1em 0; padding-left: 2em; }}
        li {{ margin: 0.5em 0; }}
        code {{
            background-color: #f4f4f4;
            padding: 0.2em 0.4em;
            border-radius: 3px;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 0.9em;
        }}
        pre {{
            background-color: #f4f4f4;
            padding: 1em;
            border-radius: 5px;
            overflow-x: auto;
        }}
        pre code {{
            background-color: transparent;
            padding: 0;
        }}
        blockquote {{
            border-left: 4px solid #ddd;
            padding-left: 1em;
            margin-left: 0;
            color: #666;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 0.5em 1em;
            text-align: left;
        }}
        th {{
            background-color: #f4f4f4;
            font-weight: 600;
        }}
        hr {{
            border: none;
            border-top: 1px solid #eee;
            margin: 2em 0;
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>
"""

        # Create CSS for page layout
        page_css = CSS(
            string=f"""
            @page {{
                size: {page_size};
                margin: 2cm;
            }}
        """
        )

        # Render PDF
        html_doc = HTML(string=html_template)
        pdf_bytes = html_doc.write_pdf(stylesheets=[page_css])

        # Encode PDF bytes as base64 for transport
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        return {
            "generic_blob": {
                "data": {
                    "format": "pdf",
                    "encoding": "base64",
                    "bytes": pdf_base64,
                    "title": title,
                }
            }
        }

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "output_format": "pdf",
                "title": "Research Evaluation Report",
                "page_size": "A4",
                "include_charts": False,
                "sections": ["executive_summary", "evaluations", "findings"],
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
                        "This executive summary provides an overview of the concept evaluation results. "
                        "Concept B demonstrates stronger alignment with customer needs, particularly in "
                        "relevance (9/10) and uniqueness (8/10) compared to Concept A. Based on these findings, "
                        "we recommend advancing Concept B to the next stage of development.",
                        "\n\n## Detailed Analysis\n\nThe evaluation was conducted across three key dimensions: "
                        "appeal, relevance, and uniqueness. Each concept was assessed by a panel of 5 experts "
                        "using a standardized scoring rubric. Results show clear differentiation between concepts, "
                        "with Concept B outperforming in 2 out of 3 criteria.",
                    ]
                },
            },
            "expected_output": {
                "generic_blob": {
                    "data": {
                        "format": "pdf",
                        "encoding": "base64",
                    }
                }
            },
        }
