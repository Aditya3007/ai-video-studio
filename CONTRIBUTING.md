# Contributing to AI Video Studio

This document provides guidelines for contributors (human and AI agents) working on the AI Video Studio project.

## Project Overview

AI Video Studio is a production-oriented AI video generation platform that transforms topics or stories into YouTube Shorts with persistent characters, locations, and series continuity.

**Key Characteristics**:
- Series-aware with persistent universe
- End-to-end automation from story to published video
- Provider-agnostic AI integration
- Quality-focused with AI-powered QA
- Cost-conscious with tracking and optimization

## For AI Agents

### Understanding the Project

Before making changes, AI agents should:

1. **Read the Documentation**:
   - `PRODUCT.md` - Understand the product vision and requirements
   - `ARCHITECTURE.md` - Understand the intended architecture
   - `ROADMAP.yaml` - Understand the phases and tasks
   - `PROJECT_STATUS.yaml` - Check current progress

2. **Check Current Status**:
   - Always check `PROJECT_STATUS.yaml` to see the current phase and task
   - Do not skip ahead to later phases without completing prerequisites
   - Respect task dependencies in `ROADMAP.yaml`

3. **Follow the Roadmap**:
   - Work on tasks in the order defined in `ROADMAP.yaml`
   - Mark tasks as `IN_PROGRESS` when starting work
   - Mark tasks as `COMPLETED` only when acceptance criteria are met
   - Update `PROJECT_STATUS.yaml` when changing task status

### Working on Tasks

#### Task Selection

1. Find the current task in `PROJECT_STATUS.yaml`
2. Verify the task is `READY` or `IN_PROGRESS`
3. Check dependencies are completed
4. Read the task's acceptance criteria in `ROADMAP.yaml`

#### Implementation

1. **Explore the Codebase**: Understand existing patterns and conventions
2. **Follow Existing Patterns**: Mimic the code style, libraries, and patterns already in use
3. **Add Dependencies**: Only add new dependencies if the project already uses similar libraries
4. **Write Tests**: If the project has test infrastructure, write tests for new functionality
5. **Update Documentation**: Update relevant documentation if your change affects architecture or behavior

#### Completion

1. Verify all acceptance criteria are met
2. Run any available verification commands (lint, test, build)
3. Update the task status in `ROADMAP.yaml` to `COMPLETED`
4. Update `PROJECT_STATUS.yaml`:
   - Add task to `completed_tasks`
   - Remove from `in_progress_tasks` if present
   - Update `overall_progress`
   - Update `last_updated`
5. Set the next task to `READY` if its dependencies are complete

### Code Conventions

#### General
- Follow the existing code style in the project
- Use clear, descriptive variable and function names
- Keep functions focused and concise
- Add comments only when necessary (the code should be self-documenting)
- Avoid premature optimization

#### Specific Guidelines (Once Tech Stack is Chosen)
- **Python**: Follow PEP 8, use type hints
- **TypeScript/Node.js**: Follow ESLint rules, use strict mode
- **Database**: Use migrations for schema changes
- **API**: Follow RESTful principles, use consistent response formats

### Testing

- Write tests for new functionality
- Ensure existing tests pass
- Test edge cases and error conditions
- Keep tests fast and reliable

### Error Handling

- Handle errors gracefully
- Provide meaningful error messages
- Log errors appropriately
- Don't silently swallow errors

### Security

- Never commit API keys or secrets
- Validate all user inputs
- Use parameterized queries for database operations
- Follow security best practices for the chosen stack

## For Human Contributors

### Getting Started

1. Fork the repository
2. Clone your fork
3. Set up the development environment (see below)
4. Create a branch for your work

## Local Development Setup

### Prerequisites

- **Python 3.11+**: Install via [pyenv](https://github.com/pyenv/pyenv) or [python.org](https://www.python.org/)
- **Node.js 18+**: Install via [nvm](https://github.com/nvm-sh/nvm) or [nodejs.org](https://nodejs.org/)
- **Git**: Install via [git-scm.com](https://git-scm.com/)

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Run tests:
   ```bash
   pytest
   ```

4. Run linting:
   ```bash
   ruff check .
   ```

5. Run formatting check:
   ```bash
   black --check .
   ```

6. Format code:
   ```bash
   black .
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start development server:
   ```bash
   npm run dev
   ```

4. Run linting:
   ```bash
   npm run lint
   ```

5. Fix linting issues:
   ```bash
   npm run lint:fix
   ```

6. Run formatting check:
   ```bash
   npm run format:check
   ```

7. Format code:
   ```bash
   npm run format
   ```

8. Build for production:
   ```bash
   npm run build
   ```

### Pre-commit Hooks

Pre-commit hooks are configured to run automatically before commits. To set them up:

1. Install pre-commit (if not already installed):
   ```bash
   pip install pre-commit
   ```

2. Install the hooks:
   ```bash
   pre-commit install
   ```

3. Run hooks manually on all files:
   ```bash
   pre-commit run --all-files
   ```

The pre-commit hooks will:
- Run Ruff (Python linter) with auto-fix
- Run Black (Python formatter)
- Check for trailing whitespace
- Fix end-of-file issues
- Validate YAML files
- Check for large files
- Check for merge conflicts
- Validate TOML files

### Environment Configuration

1. Copy the example environment file and fill in values for your local environment:
   ```bash
   cp .env.example .env
   ```

2. Never commit `.env` or any local environment file that contains secrets. `.env` is ignored by Git; `.env.example` is tracked and contains placeholders only.

3. CI receives secrets through repository secrets and environment variables configured in GitHub Actions, never by committing them to the repository.

4. Do not place secrets in frontend code. Frontend builds are public and must never contain API keys or credentials.

5. Secrets must never appear in logs, URLs, error messages, or API responses. The backend configuration masks secret values in representations and avoids dumping them.

### Transferring the Project

The project can be packaged for transfer to another machine using the included utility:

```bash
./scripts/package_project.sh
```

Options:

- `./scripts/package_project.sh --dry-run` — preview what would be included/excluded without creating the archive.
- `./scripts/package_project.sh /path/to/output` — write the archive to a custom directory or `.zip` path.
- `./scripts/package_project.sh --validate path/to/archive.zip` — verify an existing archive.

What is intentionally excluded:

- Installed dependencies (`node_modules`, Python `.venv`, egg-info).
- Build artifacts (`frontend/dist`, `.vite`, compiled Python files).
- Caches (`.pytest_cache`, `.ruff_cache`, `__pycache__`).
- Local databases and runtime storage (`*.db`, `storage/`).
- Secrets (`.env`, `.env.local`, `.env.*.local`, keys, credentials).
- Git history and machine-specific files.

`.env.example` is preserved and must be copied to `.env` on the destination laptop and filled with real values. Dependencies must be reinstalled there (`pip install -e ".[dev]"` in `backend`, `npm install` in `frontend`). The generated archive is validated automatically to ensure it does not contain forbidden artifacts.

### Storage

The backend uses a provider-neutral storage abstraction. Choose a backend with `STORAGE_BACKEND`:

- **filesystem** (default for local development):
  ```bash
  STORAGE_BACKEND=filesystem
  STORAGE_LOCAL_ROOT=storage
  ```
  Objects are stored under the configured local root using logical object keys. Path traversal is rejected.

- **s3** (for MinIO, AWS S3, or other S3-compatible services):
  ```bash
  STORAGE_BACKEND=s3
  STORAGE_BUCKET=ai-video-studio
  STORAGE_ENDPOINT=http://localhost:9000
  STORAGE_REGION=us-east-1
  STORAGE_ACCESS_KEY=your_access_key
  STORAGE_SECRET_KEY=your_secret_key
  ```
  The `boto3` and `botocore` packages are required at runtime for S3 storage. The backend does not currently depend on a running MinIO/S3 server for the default test suite.

Keys are logical, such as `series/{series_id}/characters/{character_id}/references/{filename}`. The storage backend receives the key and never allows the caller to escape the configured root or bucket.

### Universe Engine

A `Series` is the root boundary of a persistent story universe. The universe engine aggregates canonical context consumed by later pipeline stages:

- **Series** — root ownership boundary
- **World** — persistent setting, era, geography, technology, rules, culture, and timeline context
- **Visual Bible** — one-per-series canonical visual language (art style, color palette, lighting, camera, etc.)
- **Audio Bible** — one-per-series canonical audio language (voice, narration, music, sound effects, etc.)
- **Characters** — persistent identities with versioned states
- **Locations** — persistent places with versioned states
- **Story Objects** — persistent important props/artifacts

Retrieve the aggregated read model via:

```bash
GET /api/v1/series/{series_id}/universe
```

The response is a read-only snapshot. Updates to individual entities continue to use their existing CRUD endpoints. Context never leaks across series boundaries.

### Verification

To verify your setup is working:

1. Backend:
   ```bash
   cd backend
   pytest  # Should pass
   ruff check .  # Should pass
   black --check .  # Should pass
   ```

2. Frontend:
   ```bash
   cd frontend
   npm run lint  # Should pass
   npm run format:check  # Should pass
   npm run build  # Should succeed
   ```

3. Pre-commit:
   ```bash
   pre-commit run --all-files  # Should pass
   ```

### Making Changes

1. Check `PROJECT_STATUS.yaml` to understand current progress
2. Choose a task from `ROADMAP.yaml` that is `READY`
3. Create an issue (if one doesn't exist) to track your work
4. Implement the changes following the acceptance criteria
5. Test your changes thoroughly
6. Submit a pull request

### Pull Request Process

1. Use the PR template (`.github/pull_request_template.md`)
2. Reference the issue or task ID
3. Describe what you changed and why
4. Link to relevant documentation updates
5. Ensure CI checks pass
6. Request review from maintainers

### Issue Reporting

Use the appropriate issue template:
- `.github/ISSUE_TEMPLATE/feature.md` - New features
- `.github/ISSUE_TEMPLATE/bug.md` - Bug reports
- `.github/ISSUE_TEMPLATE/task.md` - General tasks

## Project Rules

### Do's
- Follow the roadmap phase order
- Update documentation when architecture changes
- Write tests for new functionality
- Keep the codebase clean and maintainable
- Ask questions if something is unclear

### Don'ts
- Skip ahead to later phases without completing prerequisites
- Mark tasks as completed without meeting acceptance criteria
- Add unnecessary dependencies
- Commit secrets or API keys
- Make breaking changes without discussion

## Communication

- For questions about architecture, reference `ARCHITECTURE.md`
- For questions about product requirements, reference `PRODUCT.md`
- For questions about task priorities, reference `ROADMAP.yaml`
- For implementation guidance, reference existing code patterns

## Story Intelligence

The `app.story_intelligence` package defines the boundary between story intake and future AI-driven generation.

- `Story` captures the raw user-supplied source; `StoryVersion` preserves immutable source versions.
- `StoryAnalysisResult` is the provider-neutral structured representation consumed by the next pipeline stage.
- `StoryAnalyzer` is a replaceable contract. `DeterministicStoryAnalyzer` works locally without any network; `AIStoryAnalyzer` delegates to an `LLMProvider`.
- `LLMProvider` is a provider-neutral adapter contract. `FakeLLMProvider` runs offline for tests. OpenAI, Anthropic, Gemini, and local-model adapters can be added later without changing the story domain.
- `StoryEntityResolver` maps story entities to canonical universe entities without mutation or AI. Canonical IDs are never invented by the LLM.
- Future `ScreenplayGenerator` implementations will consume `StoryAnalysisResult` and remain provider-agnostic.

Select the analyzer through `?mode=deterministic` (default) or `?mode=ai`. Set `LLM_PROVIDER=fake` in the environment to run the AI path offline with the fake provider.

## Production Planning

The production planning hierarchy is `Series → Episode → Scene → Shot → ShotSpecification → Asset`.

- `EpisodeScenePlanner` / `EpisodePlanningService` break an Episode into ordered Scenes using a `ScenePlannerStrategy`.
- `ShotPlanningService` breaks a Scene into ordered Shots using a `ShotPlannerStrategy`.
- `DeterministicScenePlanner` and `DeterministicShotPlanner` are the default offline strategies; they derive scenes/shots from existing source text.
- Future AI-assisted planners can implement the same strategy contracts without changing the production domain.
- `EpisodePlanningService.plan_and_create` and `ShotPlanningService.plan_and_create` reject overwriting existing records unless `replace=True` is explicitly passed.
- Ordering is explicit via `sequence_order` and `scene_number`/`shot_number`.
- Records are owned by their parent (`Scene` by `Episode`, `Shot` by `Scene`) and cannot cross series boundaries.
- `ShotSpecification` is a provider-neutral production contract describing intent and constraints (aspect ratio, duration, canonical refs, output constraints). Generation providers are future adapters and are not part of the planning domain.
- `Asset` is a provider-neutral domain for production artifacts (image, video, audio, storyboard, keyframe, thumbnail, reference). Assets are owned by a `Series` and reference canonical `Character`/`Location`/`StoryObject` entities by application-owned UUIDs. Assets store provider-neutral storage keys for future generation adapters.
- `ImageGenerationProvider` is a provider-neutral boundary for image generation. The application builds `ImageGenerationRequest` objects from `ShotSpecification`/Asset data and receives `ImageGenerationResult` objects. Adapters for real providers live behind this interface; only `FakeImageGenerationProvider` is implemented for tests.
- `VideoGenerationProvider` is the provider-neutral boundary for video generation. The application builds `VideoGenerationRequest` objects (supporting prompt, keyframes, reference assets, duration, aspect ratio, and motion guidance) and receives `VideoGenerationResult` objects containing `VideoReference` artifacts. Only `FakeVideoGenerationProvider` is implemented for offline tests; future adapters (Runway, Kling, Luma, Sora, Veo, local) are hidden behind this interface.
- `ImageToVideoService` converts an approved storyboard/keyframe `Asset` into a `VideoGenerationRequest`. It validates series/shot ownership and asset approval, preserves canonical references through `ReferenceAssetResolver`, maps `ShotSpecification` duration/aspect ratio/motion into provider-neutral fields, and dispatches through `VideoGenerationService`.
- `VideoGenerationJobService` provides a persistent provider-neutral video generation job lifecycle (`QUEUED` → `RUNNING` → `SUCCEEDED`/`FAILED`/`CANCELLED`) with bounded retry semantics and deterministic state transitions. It wraps `ImageToVideoService` for execution while remaining compatible with future asynchronous worker integration.
- `VideoClipValidator` validates generated `VideoReference` metadata against `VideoGenerationRequest`/ `ShotSpecification` constraints (content type, dimensions, aspect ratio, duration within tolerance). `VideoClipStorageService` stores valid clips through the existing `StorageBackend` and persists them as `Asset` records of type `VIDEO`, preserving series ownership, source asset, and job traceability in `asset_metadata`. Failed validation does not create a video asset.
- `Voice` is a provider-neutral series-owned voice identity for narration and dialogue. It may be associated with a canonical `Character` but does not rely on a vendor-specific voice ID as canonical identity. `Narration` is a provider-neutral dialogue/narration item tied to `Episode`/`Scene`/`Shot` (when applicable), `Voice`, `Character`, and an optional generated `Asset` of type `AUDIO`. `VoiceService` and `NarrationService` enforce series ownership and canonical-reference validation; future P7-T02 TTS adapters consume this domain.
- `StoryboardService` builds a provider-neutral `ImageGenerationRequest` from a `ShotSpecification`, dispatches it through `ImageGenerationService`, and stores the result as a storyboard `Asset`.
- `ReferenceAssetResolver` maps canonical `Character`/`Location`/`StoryObject` references to eligible visual reference `Asset`s in the same series. The resolved Asset IDs are passed through the existing provider-neutral `ImageGenerationRequest.reference_asset_ids` field.
- `ImageGenerationJob` models a persistent provider-neutral job lifecycle (`QUEUED` → `RUNNING` → `SUCCEEDED`/`FAILED`/`CANCELLED`) with retry/attempt tracking. Execution state is separate from `ApprovalStatus` (`PENDING`/`APPROVED`/`REJECTED`). `ImageGenerationJobService` wraps synchronous execution today while remaining compatible with future async workers. `StoryboardService` is reused to build the provider-neutral request and persist generated storyboard `Asset`s.
- Canonical entity references in scene, shot, and asset plans are resolved through `StoryEntityResolver` and are never invented by generated output.

## License

By contributing to this project, you agree that your contributions will be licensed under the project's license (to be determined).

## Acknowledgments

This project follows a structured, phase-based approach to ensure quality and maintainability. Thank you for contributing!
