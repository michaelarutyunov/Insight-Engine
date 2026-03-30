"""Advise API — research question to method recommendation.

Exposes Stages 1-3 of the ResearchAdvisor pipeline as well as endpoints
for inspecting available reasoning profiles.

All three POST endpoints accept an optional ``profile`` query parameter
that overrides the default reasoning profile used by the advisor.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from chat.research_advisor import ResearchAdvisor
from reasoning.profiles import ReasoningProfile, list_profiles, load_profile
from schemas.advise import (
    CharacterizeRequest,
    CharacterizeResponse,
    MatchRequest,
    MatchResponse,
    ProfileDetailResponse,
    ProfileListResponse,
    ProfileSummary,
    RecommendRequest,
    RecommendResponse,
)

router = APIRouter(tags=["advise"])

# Base directory for reasoning profiles (project root).
_PROFILES_DIR = Path(__file__).resolve().parent.parent.parent / "reasoning_profiles"

# Lazily cached default profile.
_default_profile: ReasoningProfile | None = None


def _get_default_profile() -> ReasoningProfile:
    """Load and cache the default reasoning profile."""
    global _default_profile
    if _default_profile is None:
        path = _PROFILES_DIR / "default" / "profile.yaml"
        if not path.is_file():
            raise FileNotFoundError(f"Default profile not found at {path}")
        _default_profile = load_profile(path)
    return _default_profile


def _resolve_profile(profile_name: str | None) -> ReasoningProfile:
    """Return the reasoning profile to use for this request.

    If *profile_name* is ``None``, returns the cached default.
    Otherwise loads ``reasoning_profiles/{profile_name}/profile.yaml``.
    """
    if profile_name is None:
        return _get_default_profile()

    path = _PROFILES_DIR / profile_name / "profile.yaml"
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Reasoning profile '{profile_name}' not found.",
        )
    return load_profile(path)


def _make_advisor(profile: ReasoningProfile) -> ResearchAdvisor:
    """Create a ResearchAdvisor using the engine registry as block_registry."""
    # Import here to avoid circular imports at module load time.
    from engine import registry as _registry

    _registry._ensure_loaded()
    return ResearchAdvisor(block_registry=_registry, reasoning_profile=profile)


# ---------------------------------------------------------------------------
# Stage 1 — characterize
# ---------------------------------------------------------------------------


@router.post("/advise/characterize", response_model=CharacterizeResponse)
async def characterize(
    request: CharacterizeRequest,
    profile: str | None = Query(None, description="Override reasoning profile name"),
) -> CharacterizeResponse:
    """Stage 1: research question + data context -> ProblemProfile."""
    reasoning_profile = _resolve_profile(profile)
    advisor = _make_advisor(reasoning_profile)
    result = await advisor.characterize_problem(
        research_question=request.research_question,
        data_context=request.data_context,
    )
    return CharacterizeResponse(profile=result)


# ---------------------------------------------------------------------------
# Stage 2 — match
# ---------------------------------------------------------------------------


@router.post("/advise/match", response_model=MatchResponse)
async def match(
    request: MatchRequest,
    profile: str | None = Query(None, description="Override reasoning profile name"),
) -> MatchResponse:
    """Stage 2: ProblemProfile -> ranked MethodCandidates."""
    reasoning_profile = _resolve_profile(profile)
    advisor = _make_advisor(reasoning_profile)
    candidates = await advisor.match_candidates(profile=request.profile)
    return MatchResponse(candidates=candidates)


# ---------------------------------------------------------------------------
# Stage 3 — recommend
# ---------------------------------------------------------------------------


@router.post("/advise/recommend", response_model=RecommendResponse)
async def recommend(
    request: RecommendRequest,
    profile: str | None = Query(None, description="Override reasoning profile name"),
) -> RecommendResponse:
    """Stage 3: candidates + constraints -> selected method + rationale."""
    reasoning_profile = _resolve_profile(profile)
    advisor = _make_advisor(reasoning_profile)
    recommendation = await advisor.recommend(
        candidates=request.candidates,
        constraints=request.constraints,
    )
    return RecommendResponse(recommendation=recommendation)


# ---------------------------------------------------------------------------
# Reasoning profiles — listing and detail
# ---------------------------------------------------------------------------


@router.get("/reasoning-profiles", response_model=ProfileListResponse)
async def get_profiles() -> ProfileListResponse:
    """List available reasoning profile names and descriptions."""
    names = list_profiles(_PROFILES_DIR)
    summaries: list[ProfileSummary] = []
    for name in names:
        path = _PROFILES_DIR / name / "profile.yaml"
        loaded = load_profile(path)
        summaries.append(ProfileSummary(name=loaded.name, description=loaded.description))
    return ProfileListResponse(profiles=summaries)


@router.get("/reasoning-profiles/{name}", response_model=ProfileDetailResponse)
async def get_profile(name: str) -> ProfileDetailResponse:
    """Return the full reasoning profile for the given name."""
    path = _PROFILES_DIR / name / "profile.yaml"
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Reasoning profile '{name}' not found.",
        )
    loaded = load_profile(path)
    return ProfileDetailResponse(profile=loaded)
