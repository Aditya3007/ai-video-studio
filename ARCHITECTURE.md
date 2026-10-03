# AI Video Studio - Architecture

## High-Level Architecture

AI Video Studio follows a modular, service-oriented architecture with clear separation of concerns. The system is organized into layers:

```
┌─────────────────────────────────────────────────────────────┐
│                     Studio UI (Web)                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   API Gateway / REST API                    │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  Core Engine  │    │   Asset Store │    │  QA Engine    │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Provider Abstraction Layer                     │
└─────────────────────────────────────────────────────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   OpenAI      │    │   Anthropic   │    │ Stable Diff.  │
└───────────────┘    └───────────────┘    └───────────────┘
```

## Core Components

### 1. API Layer

**Responsibilities**: HTTP API, request validation, authentication, rate limiting

**Key Endpoints**:
- Series management (CRUD)
- Character/Location management (CRUD with asset upload)
- Story generation (topic/story input)
- Production pipeline control (start, monitor, cancel)
- Video preview and export
- QA reports
- Cost tracking

**Technology**: REST API with JSON, OpenAPI/Swagger documentation

### 2. Core Engine

The orchestration layer that coordinates the entire production pipeline.

**Subcomponents**:

#### 2.1 Series/Universe Engine
- Manages series, episodes, characters, locations
- Enforces consistency rules
- Tracks asset dependencies
- Maintains continuity context

#### 2.2 Story Engine
- Topic-to-plot generation (LLM)
- Story-to-screenplay adaptation (LLM)
- Screenplay-to-scenes breakdown
- Continuity context loading from previous episodes

#### 2.3 Production Planner
- Scene-to-shots breakdown
- Camera angle and composition planning
- 9:16 aspect ratio planning
- Production checklist generation (required assets)

#### 2.4 Visual Generation Coordinator
- Coordinates character/location image generation
- Keyframe generation per shot
- Visual consistency validation
- Manages generation queues and retries

#### 2.5 Video Generation Coordinator
- Keyframe-to-video generation
- Video quality validation
- Regeneration pipeline for failed segments
- Manages expensive operations with cost tracking

#### 2.6 Audio Generation Coordinator
- Text-to-speech for dialogue (character voices)
- Background music generation/selection
- Sound effects generation/selection
- Audio mixing and mastering

#### 2.7 Video Assembly Engine
- Canonical timeline/assembly model (P8-T01)
  - `VideoAssembly` and `AssemblyItem` entities
  - Deterministic shot sequencing with temporal placement
  - Audio-video track/layer metadata
- FFmpeg rendering pipeline (P8-T02)
  - `FFmpegVideoRenderer` consumes `VideoAssembly` timeline
  - 9:16 output with scale/crop to 1080x1920
  - Audio mixing for narration, music, and SFX
  - Produces transient working MP4; no final artifact persistence
- Caption/subtitle timing and burn-in (P8-T03)
  - `Caption` entity linked to `Narration` and `VideoAssembly`
  - Deterministic `start_time_seconds` / `end_time_seconds` timing
  - ASS subtitle generation with word-wrapping and style metadata
  - `FFmpegVideoRenderer` burns captions via the `ass` filter
  - Unicode and special-character escaping for safe rendering
- Final video export and artifact lifecycle (P8-T04)
  - `FinalExportService` runs `FFmpegVideoRenderer` and persists the MP4
  - `StorageBackend` writes `exports/{series_id}/{assembly_id}/final.mp4`
  - Final `Asset` linked to `VideoAssembly` via `final_asset_id`
  - Assembly transitions `RENDERING → RENDERED`; failures remain `FAILED`
- Continuity rules engine (P9-T01)
  - `ContinuityService` evaluates deterministic rules over canonical + production state
  - Reuses `UniverseContextService` and existing `ShotSpecification` validators
  - Returns structured `ContinuityFinding` results; no persistence, no AI
- AI visual/narrative QA (P9-T02)
  - `AIQAService` constructs bounded canonical/production context
  - `AIQAProvider` protocol with `FakeAIQAProvider` for offline tests
  - `AIQAFinding` extends `ContinuityFinding` with confidence/source
  - Result validation rejects cross-series and malformed provider output
- QA workflow orchestration (P9-T03)
  - `QAWorkflowService` composes `ContinuityService` + `AIQAService`
  - Aggregates, deduplicates, and deterministically orders findings
  - Produces `PASS` / `WARN` / `FAIL` / `DEGRADED` overall status
- Regeneration and issue resolution loop (P9-T04)
  - `IssueResolutionService` (`app/services/issue_resolution_service.py`) turns `ContinuityFinding` / `AIQAFinding` results into persistent `QAIssue` and `QAResolutionAction` records
  - `QAIssue` states: `OPEN`, `QUEUED`, `REGENERATING`, `RECHECKING`, `RESOLVED`, `MAX_ATTEMPTS_REACHED`, `BLOCKED`, `MANUALLY_RESOLVED`
  - `ResolutionAction` types: `REGENERATE_IMAGE`, `REGENERATE_VIDEO`, `REGENERATE_TTS`, `RE_RUN_QA`, `MANUAL_REVIEW`
  - Regeneration dispatches to existing `ImageGenerationJobService`, `VideoGenerationJobService`, and `NarrationGenerationService`
  - Re-QA reruns deterministic continuity for the affected shot/episode and marks the issue `RESOLVED` only when the matching finding disappears
  - Bounded attempts (`max_attempts`) prevent uncontrolled loops; `MAX_ATTEMPTS_REACHED` stops automatic regeneration
  - `EpisodeBudgetService` and `GenerationCostService` remain authoritative for budget/cost on every regeneration
  - `AuditService` records issue lifecycle events (`QA_ISSUE_CREATED`, `REGENERATION_*`, `QA_*`)
  - API routes under `/api/v1/series` for creating, listing, resolving, requesting, and executing issues/actions
  - P9-T01 owns deterministic continuity, P9-T02 owns AI QA, P9-T03 owns workflow aggregation, P9-T04 owns remediation; P12 owns retry/idempotency/audit, P14 owns budget/cost/selection
- Studio backend APIs (P10-T01)
  - `StudioService` aggregates series/episode/scene/shot production state
  - Reuses existing domain services and schemas
  - Provides overview and production endpoints under `/api/v1/series/{id}/studio`
  - No frontend UI implemented

#### 2.8 Pipeline Orchestrator
- End-to-end pipeline execution
- Parallel processing of independent tasks
- Checkpoint and resume capability
- Retry logic with exponential backoff

### 3. Asset Store

**Responsibilities**: File storage, metadata tracking, CDN integration

**Asset Types**:
- Character visual references
- Location visual references
- Generated images (keyframes)
- Generated videos (shots, final)
- Audio files (dialogue, music, SFX)
- Thumbnails

**Storage Options**:
- Local filesystem (development)
- S3-compatible storage (production)
- CDN integration for delivery

### 4. QA Engine

**Responsibilities**: Quality assurance, continuity checking, scoring

**Subcomponents**:

#### 4.1 Visual Continuity Checker
- Character appearance consistency
- Location consistency
- Lighting and color consistency
- Costume/prop consistency

#### 4.2 Story Continuity Checker
- Plot hole detection
- Character behavior consistency
- Timeline consistency
- Reference consistency

#### 4.3 Quality Scorer
- Visual quality score
- Audio quality score
- Story coherence score
- Overall composite score

#### 4.4 Report Generator
- Issue listing with timestamps
- Severity classification
- Fix recommendations
- Pass/fail determination

### 5. Provider Abstraction Layer

**Responsibilities**: Unified interface for AI providers, cost tracking, provider selection

**Interface Design**:

```typescript
interface Provider {
  name: string;
  type: 'text' | 'image' | 'audio' | 'video';

  // Text generation
  generateText(prompt: string, options: TextOptions): Promise<TextResponse>;

  // Image generation
  generateImage(prompt: string, options: ImageOptions): Promise<ImageResponse>;

  // Audio generation
  generateAudio(text: string, options: AudioOptions): Promise<AudioResponse>;

  // Video generation
  generateVideo(input: VideoInput, options: VideoOptions): Promise<VideoResponse>;

  // Cost tracking
  estimateCost(operation: string, params: any): Promise<number>;
}
```

#### Provider Registry (P11-T01)

- `ProviderRegistry` (`app/provider_registry`) is an application/infrastructure layer for registering and resolving provider implementations by category and ID.
- `ProviderType` enum distinguishes categories: `llm`, `image_generation`, `video_generation`, `tts`, `audio_generation`, `ai_qa`.
- Provider IDs are stable configuration strings (e.g., `fake`) independent of Python class names.
- Supports `register(type, id, provider)`, `resolve(type, id)`, `has(type, id)`, and `list(type)` with typed overloads for each provider protocol.
- Existing factories (LLM, image, video, TTS, audio) resolve `fake` defaults via the registry while preserving prior `ValueError`/`NotImplementedError` behavior.
- P11-T01 does not introduce real provider SDKs, credentials, database persistence, health checks, or fallback logic.

#### Model Registry (P11-T02)

- `ModelRegistry` (`app/model_registry`) is a provider-neutral layer for model metadata, capabilities, and runtime configuration.
- `ModelDefinition` references a provider by `provider_type` + `provider_id` without embedding provider-specific implementation objects.
- `ModelCapabilityType` enumerates provider-neutral capabilities (e.g., `text_generation`, `image_generation`, `image_to_video`, `speech_synthesis`, `narrative_qa`) with optional `constraints`.
- `ModelConfiguration` stores runtime parameters per model; it rejects secret-like keys and is separate from `Settings`/secret handling.
- `ModelRegistry` supports `register`, `resolve`, `list` (by provider type and enabled state), `list_by_capability`, `get_configuration`, and `set_configuration`.
- Isolated registry instances are used in tests; no database persistence or vendor SDK dependencies are introduced in P11-T02.

#### Provider Health / Fallback (P11-T03)

- `HealthStatus` enumerates `healthy`, `degraded`, `unavailable`, and `unknown`.
- `HealthStore` maintains in-memory provider/model health state keyed by `(provider_type, provider_id, model_id)`.
- `HealthChecker` protocol is provider-neutral; `StaticHealthChecker` and `StoreBackedHealthChecker` provide deterministic offline implementations.
- `FallbackSelector` uses `ModelRegistry` and `HealthStore` to deterministically select an eligible model by provider type, preferred model, required capabilities, and `FallbackPolicy`.
- Fallback respects category isolation, model enablement, capability compatibility, and explicit policy for degraded/unknown states.
- No background monitoring, persistent health history, or vendor health SDK integrations are introduced in P11-T03.

#### Prompt / Model Configuration Tracking (P11-T04)

- `PromptVersion` is an immutable, provider-neutral prompt version with `prompt_id`, `version`, `content`, `purpose`, `operation`, `variables`, and `metadata`.
- `PromptRegistry` registers prompt versions, resolves specific/current versions, and rejects duplicate versions.
- `PromptRenderer` substitutes `{{ variable }}` placeholders at runtime without mutating the stored `PromptVersion`.
- `ModelConfigurationVersion` computes a deterministic SHA-256 identity from a canonical JSON representation of a `ModelConfiguration`, excluding secret keys.
- `GenerationConfigurationReference` captures the stable `(prompt_id, prompt_version, model_id, model_configuration_version, provider_type, provider_id)` tuple for reproducibility.
- `ai_tracking` builds on `ModelRegistry` and `ModelConfiguration` without duplicating model definitions or introducing persistence.

#### Async Orchestration (P12-T01)

- `Orchestrator` (`app/orchestration`) provides a provider-neutral boundary for submitting and executing production jobs asynchronously.
- `JobTask` and `JobType` identify queued work; `Worker` protocol supports `ImmediateWorker` (synchronous) and `ThreadedWorker` (thread pool) implementations.
- `Orchestrator` creates `ImageGenerationJob` / `VideoGenerationJob` records in `QUEUED` state and delegates execution to existing `ImageGenerationJobService` / `VideoGenerationJobService` in worker threads.
- Job lifecycle states (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`) are preserved on the existing generation-job models.
- Series isolation is enforced via the existing service `_get_job` checks.
- No new persistence layer is introduced; orchestration state is stored in the existing job tables.

#### Retries, Idempotency & Resumability (P12-T02)

- `ExecutionGuard` provides deterministic, application-level idempotency and recovery checks on `ImageGenerationJob` / `VideoGenerationJob` state.
- Worker execution is skipped for `RUNNING`, `SUCCEEDED`, and `CANCELLED` jobs and retried only for `FAILED` jobs with remaining attempts.
- `Orchestrator.retry_image_generation` / `retry_video_generation` enqueue explicit retries while enforcing `max_attempts` bounds.
- `Orchestrator.resume_image_generation` / `resume_video_generation` recover `QUEUED` jobs, reset stale `RUNNING` jobs, and retry `FAILED` jobs that are still eligible.
- Retry counts are preserved on the existing job models; no new persistence or locking infrastructure is introduced.

#### Episode End-to-End Production Pipeline (P12-T03)

- `EpisodeProductionService` (`app/services/episode_production.py`) composes the existing domain services into a single provider-neutral episode production workflow.
- Deterministic stages include `PLANNING`, `STORYBOARD`, `IMAGE_GENERATION`, `VIDEO_GENERATION`, `AUDIO`, `QA`, `ASSEMBLY`, `EXPORT`, and `COMPLETED`.
- The pipeline reuses existing storyboard, image-generation, video-generation, narration, QA, video assembly, FFmpeg rendering, and final export services.
- Existing assets and succeeded generation jobs are reused when present; new jobs are submitted through the P12-T01 `Orchestrator` with `ImmediateWorker`/`ThreadedWorker`.
- QA results in `FAIL` or `DEGRADED` block final export; `PASS` is required to proceed.
- No new database tables or migrations were introduced.

#### Production Observability and Audit Trail (P12-T04)

- `AuditEvent` (`app/models/audit_event.py`) is an append-only record of production activity, linked to `Series`, `Episode`, `Scene`, `Shot`, `Asset`, and generation jobs.
- `AuditService` (`app/services/audit_service.py`) provides provider-neutral `record` and `get_history` operations; metadata and error strings are sanitized to redact API keys, tokens, authorization headers, and other secrets.
- `EpisodeProductionService` emits lifecycle events (`PRODUCTION_STARTED`, `STAGE_STARTED`, `STAGE_COMPLETED`, `STAGE_FAILED`, `QA_COMPLETED`, `EXPORT_COMPLETED`, `PRODUCTION_FAILED`, `PRODUCTION_COMPLETED`) and asset events (`ASSET_CREATED`, `ASSET_REUSED`) around each deterministic stage.
- `Orchestrator` emits job lifecycle events (`JOB_SUBMITTED`, `JOB_STARTED`, `JOB_COMPLETED`, `JOB_FAILED`, `JOB_RETRIED`, `JOB_RESUMED`) and propagates a `production_run_id` from the episode pipeline through `JobTask`.
- All events in a single production invocation share a stable `production_run_id`; resume/retry preserves the original run correlation while appending new events.
- Audit failures are caught by `EpisodeProductionService` and surfaced in result `warnings`; production correctness remains primary.
- Migration `f651f303d9cf_add_audit_events.py` adds the `audit_events` table and indexes; it is compatible with SQLite and PostgreSQL.

#### YouTube Publishing Abstraction (P13-T01)

- `PublishingProvider` (`app/publishing`) defines a provider-neutral contract for `publish`, `get_status`, and `cancel`.
- `PublishingRequest` and `PublishingResult` carry provider-neutral metadata (title, description, tags, visibility, Shorts flag, scheduled publish time, idempotency key) without YouTube SDK or OAuth types.
- `PublishingStatus` (`PENDING`, `UPLOADING`, `PUBLISHED`, `FAILED`, `CANCELLED`) provides an explicit lifecycle.
- `FakePublishingProvider` is a deterministic, credential-free, network-free implementation for local tests.
- `PublishingService` (`app/services/publishing_service.py`) validates Asset existence, Series ownership, final video availability, and 9:16 Shorts constraints before invoking the configured provider.
- Authentication (OAuth, tokens, client secrets) remains a provider-side concern; no credentials enter the domain models or API schemas.
- `ProviderRegistry` includes `ProviderType.PUBLISHING`, so future real adapters can replace `FakePublishingProvider` without changing domain contracts.
- A minimal `POST /api/v1/publish` endpoint exposes the service while keeping provider objects out of FastAPI responses.
- P13-T02 (AI metadata) and P13-T03 (scheduling workflow) are out of scope for this task.

#### Shorts Metadata / Thumbnail Generation (P13-T02)

- `ShortsMetadata` (`app/services/shorts_metadata_service.py`) is a provider-neutral publishing metadata contract with title, description, tags/hashtags, category, language, call-to-action, and source Episode/Story traceability.
- `DeterministicShortsMetadataGenerator` produces predictable, offline Shorts metadata from existing Series/Episode/Story context.
- `LLMShortsMetadataGenerator` reuses the existing `LLMProvider` boundary and `FakeLLMProvider` for structured, AI-generated metadata without inventing plot facts.
- `ShortsMetadataService` loads the canonical Series/Episode/Story context, sanitizes secrets, and dispatches to either deterministic or AI mode; canonical story content is never overwritten.
- `ThumbnailService` (`app/services/thumbnail_service.py`) validates an existing image/storyboard/keyframe Asset as a thumbnail candidate, enforcing Series ownership and storage availability without copying binaries.
- Generated metadata is distinct from video captions/subtitles, which remain the responsibility of the rendering pipeline.
- No publishing workflow, scheduling, or real YouTube integration is implemented; those belong to P13-T03.

#### Publishing Workflow and Scheduling (P13-T03)

- `PublishingWorkflowService` (`app/services/publishing_workflow_service.py`) coordinates the end-to-end publishing lifecycle: Episode validation, final Asset/QA publishability gate, metadata resolution via `ShortsMetadataService`, thumbnail validation via `ThumbnailService`, `PublishingRequest` construction, provider invocation through `PublishingService`, state tracking, and `AuditService` events.
- `PublishingJob` (`app/models/publishing_job.py`) persists workflow state (`READY`, `SCHEDULED`, `PUBLISHING`, `PUBLISHED`, `FAILED`, `CANCELLED`) with idempotency key, scheduled time, attempts, and provider result references.
- Publishability is enforced by verifying the Episode belongs to the Series, the Asset is a rendered `VIDEO`/`AVAILABLE` final export (`VideoAssembly` status `RENDERED` and `final_asset_id` match), and the thumbnail Asset passes `ThumbnailService` validation.
- Immediate and scheduled publications both create a `PublishingJob`; scheduled jobs remain `SCHEDULED` until `execute_due()` runs them, or `execute()` is called directly for a due job.
- State transitions are explicit (`READY→PUBLISHING`, `SCHEDULED→PUBLISHING`, `PUBLISHING→PUBLISHED/FAILED`, `FAILED→READY` via retry, etc.) and invalid transitions are rejected.
- Idempotency is provided by the `idempotency_key` unique constraint; duplicate requests with the same key return the existing job.
- `AuditService` records `PUBLICATION_REQUESTED`, `PUBLICATION_VALIDATED`, `PUBLICATION_SCHEDULED`, `PUBLICATION_STARTED`, `PUBLICATION_COMPLETED`, `PUBLICATION_FAILED`, `PUBLICATION_CANCELLED`, and `PUBLICATION_RETRIED`.
- API endpoints (`app/api/routes/publishing.py`) expose `POST /api/v1/publishing`, `GET /api/v1/publishing/{series_id}/{job_id}`, `POST /api/v1/publishing/{series_id}/{job_id}/cancel`, and `POST /api/v1/publishing/{series_id}/{job_id}/retry` with Series-scoped access controls.
- The existing `POST /api/v1/publish` endpoint from P13-T01 is preserved for direct provider calls.
- No real YouTube API, OAuth, or external upload integration is implemented; the fake provider is used for local validation.

#### Generation Cost Tracking (P14-T01)

- `GenerationCost` (`app/models/generation_cost.py`) is a provider-neutral cost record for a single AI/media generation execution. It references `Series`, `Episode`, `job_id`, `asset_id`, `generation_type`, `provider`, `model`, `cost_status`, `cost_currency`, `total_cost` (as `Decimal(19,6)`), `usage_components`, `correlation_id`, and `request_id`.
- `GenerationType` (`app/models/enums.py`) categorizes the operation generically: `TEXT`, `EMBEDDING`, `IMAGE`, `VIDEO`, `TTS`, `MUSIC`, `SFX`.
- `CostStatus` distinguishes `ESTIMATED` costs from `ACTUAL` provider usage.
- `GenerationCostService` (`app/services/generation_cost_service.py`) calculates deterministic totals from provider-neutral `CostComponent` items (`quantity × unit_price` per component, summed as `Decimal`), records costs, normalizes usage from existing provider result types, and provides Series/Episode/generation/provider/model/time-range queries and aggregations.
- Cost recording is integrated into existing generation paths without rewriting them: `ImageGenerationJobService`, `VideoGenerationJobService`, and `NarrationGenerationService` call `GenerationCostService` after a successful provider result, using the provider's own `usage` metadata and `request_id`.
- Duplicate cost records for the same tracked execution are prevented by a unique `series_id + correlation_id` constraint. A retry with the same execution identifier does not double-count; a genuinely new provider execution gets a new cost record.
- API endpoints (`app/api/routes/costs.py`) expose `GET /api/v1/costs/{series_id}` and `GET /api/v1/costs/{series_id}/episodes/{episode_id}` with Series-scoped filtering by generation type, provider, model, cost status, and time range.
- `AuditService` records `GENERATION_COST_RECORDED` for meaningful cost-accounting events; secrets/credentials are never persisted in cost records or audit metadata.
- Budget enforcement, spending alerts, monetization, ROI, cost-aware provider selection, and P14-T02/T03/T04 behaviors are explicitly out of scope.

#### Per-Episode Budget and Usage Controls (P14-T02)

- `EpisodeBudget` (`app/models/episode_budget.py`) stores per-episode generation budget and usage limits. It references `Series`, `Episode`, a `Decimal(19,6)` `budget_amount`, explicit `cost_currency`, an `active` flag, and `usage_limits` JSON.
- `BudgetReservation` (`app/models/budget_reservation.py`) holds a temporary estimated-cost reservation for a single generation execution. It references `Series`, `Episode`, `generation_type`, `job_id`, `correlation_id`, estimated/actual costs, currency, and lifecycle `status` (`RESERVED`, `SETTLED`, `RELEASED`). A unique `series_id + correlation_id` constraint makes retries idempotent.
- `BudgetStatus` and `BudgetReservationStatus` (`app/models/enums.py`) provide explicit budget lifecycle states (`UNCONFIGURED`, `WITHIN_BUDGET`, `EXHAUSTED`, `OVER_BUDGET`).
- `EpisodeBudgetService` (`app/services/episode_budget_service.py`) configures budgets, computes spend from existing `GenerationCost` records, tracks active reservations, exposes `BudgetUsage`, `BudgetCheckResult`, and enforces usage limits (`max_generations` per `GenerationType`).
- Pre-generation budget checks are integrated into `ImageGenerationJobService`, `VideoGenerationJobService`, and `NarrationGenerationService` before the provider is invoked. When no budget is configured, generation is allowed; when configured, the check blocks `BUDGET_EXCEEDED`, `USAGE_LIMIT_EXCEEDED`, and `CURRENCY_MISMATCH` conditions.
- Reservation lifecycle: a successful generation settles the reservation (removing the hold) and the actual cost is recorded via `GenerationCostService`; a failed generation releases the reservation. Actual costs are the source of truth for spend; reservations prevent concurrent over-commitment.
- API endpoints (`app/api/routes/budget.py`) expose `PUT /api/v1/series/{series_id}/episodes/{episode_id}/budget`, `GET /api/v1/series/{series_id}/episodes/{episode_id}/budget`, `GET /api/v1/series/{series_id}/episodes/{episode_id}/budget/usage`, and `POST /api/v1/series/{series_id}/episodes/{episode_id}/budget/check` with Series/Episode isolation.
- `AuditService` records `BUDGET_CONFIGURED`, `BUDGET_CHECKED`, `BUDGET_EXCEEDED`, `BUDGET_RESERVATION_CREATED`, `BUDGET_RESERVATION_RELEASED`, and `BUDGET_RESERVATION_SETTLED`. No credentials or provider secrets are persisted in budget or audit records.
- Estimation is provider-neutral and conservative: the current integration passes a zero estimated cost when no estimate is available. Budgets therefore act as a configurable cap and usage-limit gate while remaining compatible with existing fake providers. A real estimate boundary can be layered in later without changing the reservation semantics.
- P14-T03 (spending alerts/budget enforcement beyond per-episode controls), P14-T04 (cost-aware provider selection), monetization, revenue, ROI, dashboards, and automatic provider switching remain explicitly out of scope.

#### Monetization and Unit Economics Dashboard (P14-T03)

- `UnitEconomicsService` (`app/services/unit_economics_service.py`) derives read-only cost-side analytics from existing `GenerationCost`, `EpisodeBudget`, and `BudgetReservation` records. It preserves provider-neutral contracts and uses `Decimal` arithmetic for all monetary aggregation.
- Series-level economics include total actual spend, generation count, episode count, average cost per generation, cost breakdowns by `GenerationType`/provider/model, total configured budget, total reserved amount, remaining budget, and budget utilization.
- Episode-level economics include per-episode actual spend, generation counts, cost breakdowns, generation-count-by-type, budget amount, active reservations, remaining/available budget, utilization, and budget status.
- Optional filters (`generation_type`, `provider`, `model`, `start`, `end`) are supported on read-only analytics queries; budget totals are derived from persisted budget rows while spend is derived from the filtered `GenerationCost` set.
- API endpoints (`app/api/routes/unit_economics.py`) expose `GET /api/v1/series/{series_id}/economics` and `GET /api/v1/series/{series_id}/episodes/{episode_id}/economics` with Series/Episode isolation.
- React `UnitEconomicsDashboard` (`frontend/src/components/UnitEconomicsDashboard.tsx`) adds an "Economics" tab to `Studio`, showing total spend, budget, remaining budget, utilization, generation count, cost breakdowns, and episode-level breakdowns with loading/error/empty/no-budget states.
- The dashboard explicitly represents production cost economics and does not invent revenue, profit, margin, ROI, or subscription pricing because no revenue model exists in the repository. P14-T04 (cost-aware provider/model selection), payment processing, billing, revenue tracking, and automated provider switching remain out of scope.

#### Cost-Aware Provider/Model Selection (P14-T04)

- `CostAwareSelector` (`app/services/cost_aware_selector.py`) implements a provider-neutral, deterministic selection policy that ranks eligible provider/model candidates by estimated cost. It does not invoke providers and does not record actual costs.
- Candidate filtering order is: required capabilities (`ModelRegistry`), enabled state, health eligibility (`HealthStore`), and optional maximum cost. Cost ranking is applied only after capability and health filtering.
- `CostEstimator` derives an estimate from a model's `pricing` metadata (`unit`, `unit_price`, `currency`) and a generation-specific cost context (`num_images`, `duration_seconds`, `character_count`, etc.). Missing or incomplete pricing is treated as an unknown cost rather than zero cost.
- Unknown-cost candidates are excluded from cost-aware ranking by default; when `allow_unknown_cost=True` they receive a deterministic `Decimal("Infinity")` penalty, preserving deterministic tie-breaking by `model_id` if all candidates are unknown.
- The `provider_selection_mode` setting (`default` | `cost_aware`) preserves existing behavior by default. `cost_aware_allow_unknown` controls unknown-cost handling.
- `ImageGenerationProviderFactory`, `VideoGenerationProviderFactory`, and `TTSProviderFactory` accept a generation `request` and use `CostAwareSelector` when `provider_selection_mode == "cost_aware"`. Otherwise they continue returning the configured provider.
- `ImageGenerationJobService`, `VideoGenerationJobService` (via `ImageToVideoService`), and `NarrationGenerationService` continue to perform the existing `EpisodeBudgetService` check/reservation/settlement lifecycle after selection; `CostAwareSelector` is a pre-selection optimization and does not duplicate budget enforcement or `GenerationCost` recording.
- `ModelDefinition` and `ModelConfiguration` (`app/model_registry/__init__.py`) now support an optional `pricing` dictionary for configured provider/model pricing. `HealthStore` and `ModelRegistry` default singletons are exposed for selection use.
- P14-T01 continues to own actual cost recording; P14-T02 continues to own budget enforcement; P14-T03 continues to own cost visibility; P14-T04 owns selection. New provider SDK integrations, provider health redesign, billing, revenue, ML-based pricing, and load balancing remain out of scope.

**Provider Implementations**:
- OpenAI (GPT-4, DALL-E, Whisper, TTS)
- Anthropic (Claude)
- Stable Diffusion (image generation)
- ElevenLabs (TTS - optional)
- Runway/Pika (video generation - optional)

**Provider Selection Logic**:
- Cost-based routing (cheapest available for quality requirements)
- Quality-based routing (best quality for critical tasks)
- Fallback on failure
- Rate limit handling

### 6. Cost Tracker

**Responsibilities**: Track costs, estimate costs, optimize spending

**Data Tracked**:
- Cost per API call
- Cost per task type
- Cost per episode
- Cost per series
- Cost breakdown by provider

**Features**:
- Pre-generation cost estimation
- Budget alerts
- Cost optimization suggestions
- ROI calculation (revenue vs cost)

### 7. YouTube Integration

**Responsibilities**: Video upload, metadata generation, scheduling

**Features**:
- OAuth authentication
- Video upload
- Title/description/hashtag generation
- Thumbnail generation
- Scheduling
- Publish status tracking
- Revenue data retrieval

## Data Models

### Core Entities

#### Series
```yaml
id: string
name: string
description: string
genre: string
tone: string
style: string
target_audience: string
created_at: datetime
updated_at: datetime
settings:
  resolution: "1080x1920"
  frame_rate: 30
  aspect_ratio: "9:16"
  default_provider: string
  cost_budget_per_episode: number
```

#### Character
```yaml
id: string
series_id: string
name: string
description: string
traits: object
visual_references: array of Asset
voice_profile: object
created_at: datetime
updated_at: datetime
```

#### Location
```yaml
id: string
series_id: string
name: string
description: string
visual_references: array of Asset
variants: object  # day, night, weather variants
created_at: datetime
updated_at: datetime
```

#### Episode
```yaml
id: string
series_id: string
episode_number: integer
title: string
story_input: object  # topic or complete story
screenplay: object
scenes: array of Scene
status: string  # draft, in_production, qa, completed, published
created_at: datetime
updated_at: datetime
production_cost: number
```

#### Scene
```yaml
id: string
episode_id: string
scene_number: integer
location_id: string
characters: array of string  # character IDs
description: string
duration: number  # seconds
shots: array of Shot
```

#### Shot
```yaml
id: string
scene_id: string
shot_number: integer
camera_angle: string  # close-up, medium, wide, etc.
composition: string
duration: number  # seconds
keyframe: Asset
video: Asset
audio: Asset
```

#### Asset
```yaml
id: string
type: string  # character_ref, location_ref, keyframe, video, audio
file_path: string
metadata: object
cost: number
provider: string
created_at: datetime
```

## Database Schema

**Recommended**: PostgreSQL for relational data, with JSONB columns for flexible metadata.

**Key Tables**:
- series
- characters
- locations
- episodes
- scenes
- shots
- assets
- production_jobs
- cost_records
- qa_reports

**Indexes**:
- series_id on characters, locations, episodes
- episode_id on scenes, shots
- status on episodes, production_jobs
- created_at timestamps for all tables

## API Design Principles

1. **RESTful**: Use HTTP verbs correctly (GET, POST, PUT, DELETE)
2. **Versioned**: Include API version in URL (e.g., /api/v1/...)
3. **Consistent**: Use consistent naming conventions and response formats
4. **Paginated**: List endpoints support pagination
5. **Filtered**: List endpoints support filtering and sorting
6. **Validated**: All inputs validated against schemas
7. **Error Handling**: Consistent error response format with HTTP status codes

**Example Response Format**:
```json
{
  "data": { ... },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 100
  }
}
```

**Example Error Format**:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": [ ... ]
  }
}
```

## Technology Stack Recommendations

### Backend
- **Language**: Python or TypeScript/Node.js
- **Framework**: FastAPI (Python) or Express (Node.js)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy (Python) or Prisma (Node.js)
- **Task Queue**: Celery (Python) or BullMQ (Node.js)
- **File Storage**: S3-compatible (MinIO for dev, AWS S3 for prod)

### Frontend
- **Framework**: React or Next.js
- **UI Library**: shadcn/ui or Material-UI
- **State Management**: Zustand or Redux
- **Video Player**: Video.js or Plyr

### AI/ML
- **LLM**: OpenAI GPT-4, Anthropic Claude
- **Image Generation**: DALL-E 3, Stable Diffusion
- **Video Generation**: Runway Gen-2, Pika Labs, or Stable Video Diffusion
- **Audio**: OpenAI TTS, ElevenLabs (optional)

### Infrastructure
- **Containerization**: Docker
- **Orchestration**: Kubernetes (optional, for scale)
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus + Grafana
- **Logging**: Structured JSON logs

## Deployment Architecture

### Development
```
Local machine with Docker Compose:
- API server
- Database (PostgreSQL)
- Redis (for task queue)
- MinIO (for file storage)
```

### Production
```
Cloud deployment (AWS/GCP):
- Load balancer
- API servers (auto-scaling)
- Managed database (RDS/Cloud SQL)
- Managed Redis (ElastiCache/Cloud Memorystore)
- Object storage (S3/Cloud Storage)
- CDN (CloudFront/Cloud CDN)
- Task workers (separate from API servers)
```

## Security Considerations

1. **API Keys**: All provider API keys stored in environment variables or secret manager
2. **Authentication**: JWT-based authentication for API access
3. **Authorization**: Role-based access control (admin, user, read-only)
4. **Input Validation**: All user inputs validated and sanitized
5. **Rate Limiting**: API rate limiting per user and per endpoint
6. **File Upload**: File type validation, size limits, virus scanning
7. **Cost Protection**: Per-user cost limits to prevent runaway spending
8. **Audit Logging**: All sensitive operations logged for audit trail

## Scalability Considerations

1. **Horizontal Scaling**: API servers and task workers can be scaled horizontally
2. **Queue-Based Processing**: Expensive operations (video generation) use queues
3. **Asynchronous Processing**: Long-running operations return job IDs for status polling
4. **Caching**: Generated assets cached to avoid regeneration
5. **CDN**: Static assets and final videos served via CDN
6. **Database**: Read replicas for read-heavy workloads
7. **Connection Pooling**: Database connection pooling for efficiency

## Error Handling Strategy

1. **Transient Errors**: Automatic retry with exponential backoff
2. **Provider Failures**: Fallback to alternative providers when available
3. **Validation Errors**: Return 400 with detailed error messages
4. **Not Found**: Return 404 for missing resources
5. **Rate Limits**: Return 429 with retry-after header
6. **Server Errors**: Return 500 with generic error message (details logged)
7. **Job Failures**: Mark jobs as failed with error details, allow retry

## Monitoring and Observability

1. **Metrics**: Track API latency, error rates, queue lengths, generation times
2. **Logs**: Structured logs with correlation IDs for request tracing
3. **Tracing**: Distributed tracing for cross-service requests
4. **Alerts**: Alerts for high error rates, queue backups, cost overruns
5. **Health Checks**: Health check endpoints for load balancer
6. **Dashboards**: Grafana dashboards for system health and business metrics

## Future Architecture Considerations

1. **Microservices**: Consider splitting into microservices if monolith becomes unwieldy
2. **Event-Driven**: Consider event-driven architecture for better decoupling
3. **Model Fine-Tuning**: Support for custom fine-tuned models per series
4. **Multi-Region**: Multi-region deployment for latency and redundancy
5. **Edge Computing**: Edge processing for video optimization
