"""Provider-neutral YouTube Shorts metadata generation."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator
from sqlalchemy.orm import Session

from app.models import Episode, Series, Story
from app.story_intelligence.llm.errors import LLMProviderError
from app.story_intelligence.llm.factory import LLMProviderFactory
from app.story_intelligence.llm.provider import LLMProvider, LLMResponse


class ShortsMetadataError(Exception):
    """Raised when Shorts metadata generation fails."""


class ShortsMetadata(BaseModel):
    """Provider-neutral Shorts publishing metadata."""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=100)
    category: str | None = None
    language: str = "en"
    call_to_action: str | None = Field(default=None, max_length=200)
    source_episode_id: UUID
    source_story_id: UUID | None = None
    canonical_title: str | None = None
    canonical_description: str | None = None
    generator: str = "deterministic"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @computed_field
    @property
    def hashtags(self) -> list[str]:
        """Return tags normalized as hashtags."""
        return [f"#{tag}" for tag in self.tags]

    @model_validator(mode="after")
    def _normalize_tags(self) -> ShortsMetadata:
        seen: set[str] = set()
        normalized: list[str] = []
        for tag in self.tags:
            tag = tag.strip().lower()
            if not tag:
                continue
            tag = tag.replace("#", "")
            if len(tag) > 100:
                tag = tag[:100]
            if tag and tag not in seen and not _looks_like_secret(tag):
                seen.add(tag)
                normalized.append(tag)
        self.tags = normalized[:100]
        return self


class LLMShortsMetadataOutput(BaseModel):
    """Structured output expected from the LLM provider."""

    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=100)
    category: str | None = None
    language: str | None = "en"
    call_to_action: str | None = Field(default=None, max_length=200)


@runtime_checkable
class ShortsMetadataGenerator(Protocol):
    """Provider-neutral contract for Shorts metadata generators."""

    provider_id: str

    def generate(
        self,
        series: Series,
        episode: Episode,
        story: Story | None = None,
    ) -> ShortsMetadata:
        """Generate Shorts metadata for the given episode."""
        ...


def _looks_like_secret(value: str) -> bool:
    """Return True if a value resembles a credential."""
    lowered = value.lower()
    return any(
        sub in lowered
        for sub in (
            "api_key",
            "apikey",
            "token",
            "secret",
            "password",
            "authorization",
            "private_key",
            "credentials",
            "bearer",
        )
    )


def _sanitize_text(value: str | None) -> str | None:
    if not value:
        return value
    patterns = [
        (r"(Bearer\s+)[A-Za-z0-9_\-]+", r"\1***REDACTED***"),
        (r"(?i)(api[_-]?key\s*[:=]\s*)[^&\s,;]+", r"\1***REDACTED***"),
        (r"(?i)(token\s*[:=]\s*)[^&\s,;]+", r"\1***REDACTED***"),
        (r"(?i)(password\s*[:=]\s*)[^&\s,;]+", r"\1***REDACTED***"),
    ]
    for pattern, repl in patterns:
        value = re.sub(pattern, repl, value)
    return value


def _truncate(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    return value[:max_length]


class DeterministicShortsMetadataGenerator:
    """Local, deterministic Shorts metadata generator for tests/offline use."""

    provider_id = "deterministic"

    @staticmethod
    def _extract_tags(series_name: str, episode_title: str, story_title: str | None) -> list[str]:
        words: set[str] = set()
        raw = f"{series_name} {episode_title} {story_title or ''}"
        for word in re.findall(r"[a-zA-Z0-9]+", raw):
            lower = word.lower()
            if len(lower) > 3 and not _looks_like_secret(lower):
                words.add(lower)
        tags = ["shorts"]
        series_tag = series_name.lower().replace(" ", "")
        if series_tag and not _looks_like_secret(series_tag):
            tags.append(series_tag)
        for tag in sorted(words):
            if tag not in tags:
                tags.append(tag)
        return tags[:15]

    def generate(
        self,
        series: Series,
        episode: Episode,
        story: Story | None = None,
    ) -> ShortsMetadata:
        canonical_description = _sanitize_text(
            episode.description or (story.source_content if story else None) or ""
        )
        title = _truncate(episode.title, 100) or "Untitled Short"
        description = _truncate(canonical_description or "", 5000)
        story_id = UUID(story.id) if story else None
        return ShortsMetadata(
            title=title,
            description=description,
            tags=self._extract_tags(series.name, episode.title, story.title if story else None),
            language=story.language if story else "en",
            source_episode_id=UUID(episode.id),
            source_story_id=story_id,
            canonical_title=episode.title,
            canonical_description=canonical_description,
            generator=self.provider_id,
        )


class LLMShortsMetadataGenerator:
    """AI-backed Shorts metadata generator through the existing LLMProvider."""

    provider_id = "llm"

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    @staticmethod
    def _build_prompt(series: Series, episode: Episode, story: Story | None = None) -> str:
        story_title = _sanitize_text(story.title if story else None)
        story_content = _truncate(
            _sanitize_text(story.source_content if story else None) or "", 2000
        )
        episode_title = _sanitize_text(episode.title)
        episode_description = _truncate(_sanitize_text(episode.description) or "", 1000)

        lines = [
            "Generate concise YouTube Shorts publishing metadata based only on the "
            "provided context.",
            "Do not invent plot facts. Use existing story/episode content. "
            "Distinguish metadata from canonical story content.",
            "",
            f"Series: {series.name}",
            f"Episode title: {episode_title}",
        ]
        if episode_description:
            lines.append(f"Episode description: {episode_description}")
        if story_title:
            lines.append(f"Story title: {story_title}")
        if story_content:
            lines.append(f"Story context: {story_content}")
        lines.extend(
            [
                "",
                "Return JSON matching the requested schema with: title (max 100 chars), "
                "description (max 5000 chars), tags (list of strings without #), "
                "category, language, call_to_action.",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _parse_llm_response(response: LLMResponse) -> LLMShortsMetadataOutput:
        parsed = response.parsed
        if parsed is None:
            try:
                parsed = json.loads(response.content)
            except Exception as exc:
                raise ShortsMetadataError(f"LLM response could not be parsed: {exc}") from exc
        try:
            return LLMShortsMetadataOutput(**parsed)
        except Exception as exc:
            raise ShortsMetadataError(f"LLM response schema invalid: {exc}") from exc

    def generate(
        self,
        series: Series,
        episode: Episode,
        story: Story | None = None,
    ) -> ShortsMetadata:
        prompt = self._build_prompt(series, episode, story)
        try:
            response = self._llm.generate(
                user_prompt=prompt,
                response_model=LLMShortsMetadataOutput,
            )
        except LLMProviderError as exc:
            raise ShortsMetadataError(f"LLM provider error: {exc}") from exc
        except Exception as exc:
            raise ShortsMetadataError(f"LLM generation failed: {exc}") from exc

        output = self._parse_llm_response(response)
        story_id = UUID(story.id) if story else None
        return ShortsMetadata(
            title=output.title,
            description=_truncate(_sanitize_text(output.description) or "", 5000),
            tags=output.tags,
            category=output.category,
            language=output.language or "en",
            call_to_action=output.call_to_action,
            source_episode_id=UUID(episode.id),
            source_story_id=story_id,
            canonical_title=episode.title,
            canonical_description=_sanitize_text(episode.description),
            generator=self.provider_id,
        )


class ShortsMetadataService:
    """Application service for generating YouTube Shorts metadata."""

    def __init__(
        self,
        db: Session,
        *,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._db = db
        self._llm_provider = llm_provider

    def _load_context(
        self, series_id: str, episode_id: str
    ) -> tuple[Series, Episode, Story | None]:
        series = self._db.get(Series, series_id)
        if not series:
            raise ShortsMetadataError("Series not found.")
        episode = self._db.get(Episode, episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise ShortsMetadataError("Episode not found in this series.")
        story: Story | None = None
        if episode.story_id:
            story = self._db.get(Story, episode.story_id)
            if story and str(story.series_id) != series_id:
                story = None
        return series, episode, story

    def generate(
        self,
        series_id: str,
        episode_id: str,
        *,
        mode: str = "deterministic",
    ) -> ShortsMetadata:
        """Generate Shorts metadata for an episode."""
        series, episode, story = self._load_context(series_id, episode_id)
        if mode == "deterministic":
            generator: ShortsMetadataGenerator = DeterministicShortsMetadataGenerator()
        elif mode == "ai":
            llm = self._llm_provider or LLMProviderFactory.create()
            generator = LLMShortsMetadataGenerator(llm)
        else:
            raise ShortsMetadataError(f"Unknown metadata generation mode: {mode}")
        return generator.generate(series, episode, story)
