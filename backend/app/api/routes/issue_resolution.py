"""P9-T04 QA issue resolution API routes."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.schemas.continuity import ContinuityFinding
from app.schemas.issue_resolution import (
    ExecuteActionResponse,
    ManualResolutionRequest,
    QAIssueCreateRequest,
    QAIssueListResponse,
    QAIssueResponse,
    ResolutionActionRequest,
    ResolutionActionResponse,
)
from app.services.issue_resolution_service import (
    ActionNotFoundError,
    IssueNotFoundError,
    IssueResolutionError,
    IssueResolutionService,
)

router = APIRouter(prefix="/series", tags=["issue-resolution"])


def _raise_from_issue_error(exc: Exception) -> None:
    if isinstance(exc, IssueNotFoundError):
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    if isinstance(exc, ActionNotFoundError):
        raise AppError("NOT_FOUND", str(exc), status_code=404) from exc
    if isinstance(exc, IssueResolutionError):
        raise AppError("UNPROCESSABLE_ENTITY", str(exc), status_code=422) from exc
    raise AppError("INTERNAL_ERROR", str(exc), status_code=500) from exc


@router.post("/{series_id}/qa-issues", response_model=QAIssueResponse)
def create_issue(
    series_id: UUID,
    request: QAIssueCreateRequest,
    db: DbSession,
) -> QAIssueResponse:
    """Create a structured QA issue from a finding."""
    service = IssueResolutionService(db)
    try:
        finding = ContinuityFinding(
            severity=request.severity,
            rule_id=request.rule_id,
            category=request.category,
            message=request.message,
            entity_type=request.entity_type or "UNKNOWN",
            entity_id=request.entity_id,
            metadata=request.qa_finding_metadata,
        )
        issue = service.create_issue_from_finding(
            str(series_id),
            str(request.episode_id),
            finding,
            source=str(request.source),
            scene_id=str(request.scene_id) if request.scene_id else None,
            shot_id=str(request.shot_id) if request.shot_id else None,
            asset_id=str(request.asset_id) if request.asset_id else None,
            max_attempts=request.max_attempts,
        )
        return QAIssueResponse.model_validate(issue)
    except (IssueNotFoundError, IssueResolutionError) as exc:
        _raise_from_issue_error(exc)


@router.get("/{series_id}/qa-issues", response_model=QAIssueListResponse)
def list_issues(
    series_id: UUID,
    db: DbSession,
    episode_id: UUID | None = None,
    shot_id: UUID | None = None,
    status: str | None = None,
) -> QAIssueListResponse:
    """List QA issues scoped to a series."""
    service = IssueResolutionService(db)
    issues = service.list_issues(
        str(series_id),
        episode_id=str(episode_id) if episode_id else None,
        shot_id=str(shot_id) if shot_id else None,
        status=status,
    )
    return QAIssueListResponse(issues=[QAIssueResponse.model_validate(i) for i in issues])


@router.get("/{series_id}/qa-issues/{issue_id}", response_model=QAIssueResponse)
def get_issue(
    series_id: UUID,
    issue_id: UUID,
    db: DbSession,
) -> QAIssueResponse:
    """Get a single QA issue."""
    service = IssueResolutionService(db)
    try:
        issue = service.get_issue(str(series_id), str(issue_id))
        return QAIssueResponse.model_validate(issue)
    except IssueNotFoundError as exc:
        _raise_from_issue_error(exc)


@router.post(
    "/{series_id}/qa-issues/{issue_id}/resolution", response_model=ResolutionActionResponse
)
def request_resolution(
    series_id: UUID,
    issue_id: UUID,
    request: ResolutionActionRequest,
    db: DbSession,
) -> ResolutionActionResponse:
    """Request a resolution action for a QA issue."""
    service = IssueResolutionService(db)
    try:
        action = service.request_resolution(
            str(series_id),
            str(issue_id),
            request.action_type,
            action_metadata=request.action_metadata or {},
        )
        return ResolutionActionResponse.model_validate(action)
    except (IssueNotFoundError, IssueResolutionError) as exc:
        _raise_from_issue_error(exc)


@router.post(
    "/{series_id}/resolution-actions/{action_id}/execute", response_model=ExecuteActionResponse
)
def execute_action(
    series_id: UUID,
    action_id: UUID,
    db: DbSession,
) -> ExecuteActionResponse:
    """Execute a pending resolution action."""
    service = IssueResolutionService(db)
    try:
        action = service.execute_action(str(series_id), str(action_id))
        issue = service.get_issue(str(series_id), action.issue_id)
        return ExecuteActionResponse(
            action=ResolutionActionResponse.model_validate(action),
            issue=QAIssueResponse.model_validate(issue),
        )
    except (IssueNotFoundError, ActionNotFoundError, IssueResolutionError) as exc:
        _raise_from_issue_error(exc)


@router.post("/{series_id}/qa-issues/{issue_id}/resolve", response_model=QAIssueResponse)
def resolve_manually(
    series_id: UUID,
    issue_id: UUID,
    request: ManualResolutionRequest,
    db: DbSession,
) -> QAIssueResponse:
    """Manually mark a QA issue as resolved."""
    service = IssueResolutionService(db)
    try:
        issue = service.resolve_manually(
            str(series_id),
            str(issue_id),
            resolution_note=request.resolution_note,
        )
        return QAIssueResponse.model_validate(issue)
    except (IssueNotFoundError, IssueResolutionError) as exc:
        _raise_from_issue_error(exc)
