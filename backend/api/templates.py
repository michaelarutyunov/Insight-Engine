"""
Template API endpoints.

Templates are built-in pipeline definitions that users can start from.
Templates are loaded from JSON files in the templates/ directory.
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from schemas.pipeline import PipelineSchema

router = APIRouter(tags=["templates"])

# Path to templates directory
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def load_template(template_id: str) -> PipelineSchema:
    """
    Load a template from JSON file and convert to PipelineSchema.

    Args:
        template_id: The template identifier (filename without .json extension)

    Returns:
        PipelineSchema object

    Raises:
        FileNotFoundError: If template file doesn't exist
        ValueError: If template JSON is invalid
    """
    template_file = TEMPLATES_DIR / f"{template_id}.json"

    if not template_file.exists():
        raise FileNotFoundError(f"Template not found: {template_id}")

    with open(template_file) as f:
        data = json.load(f)

    return PipelineSchema(**data)


def list_available_templates() -> list[str]:
    """
    List all available template IDs.

    Returns:
        List of template IDs (filenames without .json extension)
    """
    if not TEMPLATES_DIR.exists():
        return []

    return [f.stem for f in TEMPLATES_DIR.glob("*.json") if f.is_file()]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/templates", response_model=list[PipelineSchema])
async def list_templates() -> list[PipelineSchema]:
    """Return all available pipeline templates."""
    template_ids = list_available_templates()
    templates = []

    for template_id in template_ids:
        try:
            template = load_template(template_id)
            templates.append(template)
        except (FileNotFoundError, ValueError) as e:
            # Skip invalid templates but log the error
            print(f"Warning: Failed to load template '{template_id}': {e}")

    return templates


@router.get("/templates/{template_id}", response_model=PipelineSchema)
async def get_template(template_id: str) -> PipelineSchema:
    """
    Fetch a single template by id.

    Args:
        template_id: The template identifier (filename without .json extension)

    Returns:
        PipelineSchema object

    Raises:
        HTTPException: If template not found (404)
    """
    try:
        return load_template(template_id)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}") from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail=f"Invalid template: {err}") from err
