"""Story analysis API routes."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.api.utils import commit_or_409
from app.schemas import PaginatedResponse, StoryAnalysisResponse
from app.services.story import StoryNotFoundError
from app.services.story_analysis import StoryAnalysisNotFoundError, StoryAnalysisService
from app.story_intelligence.llm import LLMProviderError

router = APIRouter(prefix="/series/{series_id}/stories/{story_id}", tags=["story-analysis"])


def _service(db: DbSession) -> StoryAnalysisService:
    return StoryAnalysisService(db)


@router.post(
    "/versions/{version_id}/analysis",
    status_code=201,
    response_model=StoryAnalysisResponse,
)
def create_analysis(
    series_id: UUID,
    story_id: UUID,
    version_id: UUID,
    db: DbSession,
    mode: Literal["deterministic", "ai"] = "deterministic",
) -> StoryAnalysisResponse:
    """Run the selected analyzer for a StoryVersion."""
    try:
        analysis = _service(db).analyze(str(series_id), str(story_id), str(version_id), mode=mode)
    except StoryNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    except LLMProviderError as exc:
        raise AppError("PROVIDER_ERROR", str(exc), status_code=502) from exc
    except (NotImplementedError, ValueError) as exc:
        raise AppError("BAD_REQUEST", str(exc), status_code=400) from exc
    commit_or_409(db)
    db.refresh(analysis)
    return analysis


@router.get("/analysis", response_model=PaginatedResponse[StoryAnalysisResponse])
def list_analyses(
    series_id: UUID,
    story_id: UUID,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[StoryAnalysisResponse]:
    """List analysis results for a Story."""
    try:
        items, total = _service(db).list_analyses(str(series_id), str(story_id), limit, offset)
    except StoryNotFoundError as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return PaginatedResponse[StoryAnalysisResponse](
        items=[StoryAnalysisResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/analysis/{analysis_id}", response_model=StoryAnalysisResponse)
def get_analysis(
    series_id: UUID, story_id: UUID, analysis_id: UUID, db: DbSession
) -> StoryAnalysisResponse:
    """Get a specific analysis result."""
    try:
        analysis = _service(db).get_analysis(str(series_id), str(story_id), str(analysis_id))
    except (StoryNotFoundError, StoryAnalysisNotFoundError) as exc:
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    return analysis
