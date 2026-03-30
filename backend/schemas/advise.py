"""Request/response schemas for the advise API endpoints."""

from __future__ import annotations

from pydantic import BaseModel

from chat.research_advisor import MethodCandidate, ProblemProfile, Recommendation
from reasoning.profiles import ReasoningProfile

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CharacterizeRequest(BaseModel):
    """Stage 1 request: research question + optional data context."""

    research_question: str
    data_context: dict | None = None


class MatchRequest(BaseModel):
    """Stage 2 request: an already-characterized ProblemProfile."""

    profile: ProblemProfile


class RecommendRequest(BaseModel):
    """Stage 3 request: candidate methods + optional constraints."""

    candidates: list[MethodCandidate]
    constraints: dict | None = None


# ---------------------------------------------------------------------------
# Response models (thin wrappers keeping the door open for future enrichment)
# ---------------------------------------------------------------------------


class CharacterizeResponse(BaseModel):
    """Stage 1 response."""

    profile: ProblemProfile


class MatchResponse(BaseModel):
    """Stage 2 response."""

    candidates: list[MethodCandidate]


class RecommendResponse(BaseModel):
    """Stage 3 response."""

    recommendation: Recommendation


class ProfileSummary(BaseModel):
    """Lightweight summary used by the profile-listing endpoint."""

    name: str
    description: str


class ProfileListResponse(BaseModel):
    """Response for GET /reasoning-profiles."""

    profiles: list[ProfileSummary]


class ProfileDetailResponse(BaseModel):
    """Response for GET /reasoning-profiles/{name}."""

    profile: ReasoningProfile
