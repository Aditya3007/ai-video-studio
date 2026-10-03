"""Stable domain enums stored as strings in the database."""

from enum import StrEnum


class EpisodeStatus(StrEnum):
    """Lifecycle states for an episode."""

    DRAFT = "DRAFT"
    PLANNING = "PLANNING"
    IN_PRODUCTION = "IN_PRODUCTION"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class EpisodeSourceType(StrEnum):
    """Origin of the episode's story material."""

    TOPIC = "TOPIC"
    SOURCE_STORY = "SOURCE_STORY"


class StorySourceType(StrEnum):
    """Origin of the story intake."""

    COMPLETE_STORY = "COMPLETE_STORY"
    TOPIC = "TOPIC"


class StoryStatus(StrEnum):
    """Lifecycle state of a story."""

    DRAFT = "DRAFT"
    READY = "READY"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AnalysisStatus(StrEnum):
    """Lifecycle state of a story analysis result."""

    PENDING = "PENDING"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class AssetType(StrEnum):
    """Provider-neutral classification of a production asset."""

    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    STORYBOARD = "STORYBOARD"
    KEYFRAME = "KEYFRAME"
    THUMBNAIL = "THUMBNAIL"
    REFERENCE = "REFERENCE"


class AssetRole(StrEnum):
    """Role an asset plays in the production pipeline."""

    CANONICAL = "CANONICAL"
    GENERATED = "GENERATED"
    REFERENCE = "REFERENCE"
    STORYBOARD = "STORYBOARD"
    THUMBNAIL = "THUMBNAIL"


class AssetStatus(StrEnum):
    """Lifecycle state of an asset artifact."""

    PENDING = "PENDING"
    AVAILABLE = "AVAILABLE"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class ApprovalStatus(StrEnum):
    """Approval state for a generated artifact or generation job."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ImageGenerationJobStatus(StrEnum):
    """Lifecycle state of an image generation job."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class VideoGenerationJobStatus(StrEnum):
    """Lifecycle state of a video generation job."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NarrationType(StrEnum):
    """Provider-neutral classification of a narration item."""

    DIALOGUE = "DIALOGUE"
    NARRATION = "NARRATION"
    VOICEOVER = "VOICEOVER"


class NarrationStatus(StrEnum):
    """Lifecycle state of a narration item."""

    PENDING = "PENDING"
    GENERATED = "GENERATED"
    FAILED = "FAILED"


class AudioCueType(StrEnum):
    """Provider-neutral classification of an audio cue."""

    MUSIC = "MUSIC"
    SOUND_EFFECT = "SOUND_EFFECT"


class AudioCueStatus(StrEnum):
    """Lifecycle state of an audio cue awaiting or resulting from generation."""

    PENDING = "PENDING"
    GENERATED = "GENERATED"
    FAILED = "FAILED"


class AssemblyStatus(StrEnum):
    """Lifecycle state of a video assembly."""

    DRAFT = "DRAFT"
    READY = "READY"
    RENDERING = "RENDERING"
    RENDERED = "RENDERED"
    FAILED = "FAILED"


class AssemblyItemType(StrEnum):
    """Provider-neutral classification of a timeline item in a video assembly."""

    VIDEO = "VIDEO"
    NARRATION = "NARRATION"
    MUSIC = "MUSIC"
    SOUND_EFFECT = "SOUND_EFFECT"


class AssemblyTrack(StrEnum):
    """Timeline track/layer for assembly items."""

    VIDEO = "VIDEO"
    DIALOGUE = "DIALOGUE"
    MUSIC = "MUSIC"
    SFX = "SFX"


class ContinuitySeverity(StrEnum):
    """Severity of a continuity finding."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class AIQAMode(StrEnum):
    """Supported AI QA evaluation scopes."""

    NARRATIVE = "NARRATIVE"
    VISUAL = "VISUAL"


class QAWorkflowStatus(StrEnum):
    """Overall result of a QA workflow evaluation."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    DEGRADED = "DEGRADED"


class QAIssueStatus(StrEnum):
    """Lifecycle states for a structured QA regeneration issue."""

    OPEN = "OPEN"
    QUEUED = "QUEUED"
    REGENERATING = "REGENERATING"
    RECHECKING = "RECHECKING"
    RESOLVED = "RESOLVED"
    MAX_ATTEMPTS_REACHED = "MAX_ATTEMPTS_REACHED"
    BLOCKED = "BLOCKED"
    MANUALLY_RESOLVED = "MANUALLY_RESOLVED"


class ResolutionActionType(StrEnum):
    """Supported remediation actions for a QA issue."""

    REGENERATE_IMAGE = "REGENERATE_IMAGE"
    REGENERATE_VIDEO = "REGENERATE_VIDEO"
    REGENERATE_TTS = "REGENERATE_TTS"
    RE_RUN_QA = "RE_RUN_QA"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ResolutionActionStatus(StrEnum):
    """Lifecycle state of a single resolution attempt."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class QAIssueSource(StrEnum):
    """Originating QA system for a structured issue."""

    CONTINUITY = "CONTINUITY"
    AI_QA = "AI_QA"
    MANUAL = "MANUAL"


class AuditEventType(StrEnum):
    """Lifecycle events for the production audit trail."""

    PRODUCTION_STARTED = "PRODUCTION_STARTED"
    STAGE_STARTED = "STAGE_STARTED"
    STAGE_COMPLETED = "STAGE_COMPLETED"
    STAGE_FAILED = "STAGE_FAILED"
    JOB_SUBMITTED = "JOB_SUBMITTED"
    JOB_STARTED = "JOB_STARTED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"
    JOB_RETRIED = "JOB_RETRIED"
    JOB_RESUMED = "JOB_RESUMED"
    ASSET_CREATED = "ASSET_CREATED"
    ASSET_REUSED = "ASSET_REUSED"
    QA_COMPLETED = "QA_COMPLETED"
    EXPORT_COMPLETED = "EXPORT_COMPLETED"
    PRODUCTION_COMPLETED = "PRODUCTION_COMPLETED"
    PRODUCTION_FAILED = "PRODUCTION_FAILED"
    PUBLICATION_REQUESTED = "PUBLICATION_REQUESTED"
    PUBLICATION_VALIDATED = "PUBLICATION_VALIDATED"
    PUBLICATION_SCHEDULED = "PUBLICATION_SCHEDULED"
    PUBLICATION_STARTED = "PUBLICATION_STARTED"
    PUBLICATION_COMPLETED = "PUBLICATION_COMPLETED"
    PUBLICATION_FAILED = "PUBLICATION_FAILED"
    PUBLICATION_CANCELLED = "PUBLICATION_CANCELLED"
    PUBLICATION_RETRIED = "PUBLICATION_RETRIED"
    GENERATION_COST_RECORDED = "GENERATION_COST_RECORDED"
    BUDGET_CONFIGURED = "BUDGET_CONFIGURED"
    BUDGET_CHECKED = "BUDGET_CHECKED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    BUDGET_RESERVATION_CREATED = "BUDGET_RESERVATION_CREATED"
    BUDGET_RESERVATION_RELEASED = "BUDGET_RESERVATION_RELEASED"
    BUDGET_RESERVATION_SETTLED = "BUDGET_RESERVATION_SETTLED"
    QA_ISSUE_CREATED = "QA_ISSUE_CREATED"
    REGENERATION_REQUESTED = "REGENERATION_REQUESTED"
    REGENERATION_STARTED = "REGENERATION_STARTED"
    REGENERATION_SUCCEEDED = "REGENERATION_SUCCEEDED"
    REGENERATION_FAILED = "REGENERATION_FAILED"
    QA_RECHECK_STARTED = "QA_RECHECK_STARTED"
    QA_ISSUE_RESOLVED = "QA_ISSUE_RESOLVED"
    QA_ISSUE_REOPENED = "QA_ISSUE_REOPENED"
    QA_MAX_ATTEMPTS_REACHED = "QA_MAX_ATTEMPTS_REACHED"
    QA_MANUALLY_RESOLVED = "QA_MANUALLY_RESOLVED"
    QA_REGENERATION_BLOCKED = "QA_REGENERATION_BLOCKED"


class GenerationType(StrEnum):
    """Provider-neutral category of a generation operation."""

    TEXT = "TEXT"
    EMBEDDING = "EMBEDDING"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    TTS = "TTS"
    MUSIC = "MUSIC"
    SFX = "SFX"


class CostStatus(StrEnum):
    """Whether a cost record is estimated or actual."""

    ESTIMATED = "ESTIMATED"
    ACTUAL = "ACTUAL"


class BudgetStatus(StrEnum):
    """High-level state of an episode's generation budget."""

    UNCONFIGURED = "UNCONFIGURED"
    WITHIN_BUDGET = "WITHIN_BUDGET"
    EXHAUSTED = "EXHAUSTED"
    OVER_BUDGET = "OVER_BUDGET"


class BudgetReservationStatus(StrEnum):
    """Lifecycle state of a budget reservation."""

    RESERVED = "RESERVED"
    SETTLED = "SETTLED"
    RELEASED = "RELEASED"


class AuditStatus(StrEnum):
    """Outcome of an audited operation."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"


class PublishingStatus(StrEnum):
    """Lifecycle states for a publishing operation/workflow."""

    READY = "READY"
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PENDING = "PENDING"
    UPLOADING = "UPLOADING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
