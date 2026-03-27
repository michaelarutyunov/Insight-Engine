"""
Research data object schemas.

Each class corresponds to an edge data_type identifier.
When adding a new type:
  1. Add the Pydantic model here
  2. Add the identifier string to DATA_TYPES
  3. Update CLAUDE.md Edge Data Types table
"""

from pydantic import BaseModel

DATA_TYPES: set[str] = {
    "respondent_collection",
    "segment_profile_set",
    "concept_brief_set",
    "evaluation_set",
    "text_corpus",
    "persona_set",
    "generic_blob",
}


class RespondentCollection(BaseModel):
    """Survey or customer data rows."""

    rows: list[dict]


class SegmentProfileSet(BaseModel):
    """Cluster labels with descriptive profiles."""

    segments: list[dict]


class ConceptBriefSet(BaseModel):
    """Product or creative concept descriptions."""

    concepts: list[dict]


class EvaluationSet(BaseModel):
    """Scored assessments with criteria and scores."""

    evaluations: list[dict]


class TextCorpus(BaseModel):
    """Unstructured text documents."""

    documents: list[str]


class PersonaSet(BaseModel):
    """Synthetic or real persona profiles."""

    personas: list[dict]


class GenericBlob(BaseModel):
    """Fallback for untyped or experimental data."""

    data: dict
