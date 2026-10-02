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

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Fill in the required values in `.env` (most are not needed for initial development)

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

## License

By contributing to this project, you agree that your contributions will be licensed under the project's license (to be determined).

## Acknowledgments

This project follows a structured, phase-based approach to ensure quality and maintainability. Thank you for contributing!
