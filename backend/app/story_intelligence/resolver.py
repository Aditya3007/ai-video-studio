"""Deterministic story-to-universe entity resolver."""

from app.schemas.universe import UniverseContextResponse
from app.story_intelligence.schemas import ResolutionResult


def _normalize(value: str) -> str:
    return value.strip().casefold()


class StoryEntityResolver:
    """Resolves story entities to canonical universe entities without AI or mutation."""

    def __init__(self, universe_context: UniverseContextResponse) -> None:
        self._context = universe_context

    def resolve_character(self, name: str) -> ResolutionResult:
        """Resolve a story character name to a canonical character."""
        target = _normalize(name)
        matches = [
            character
            for character in self._context.characters
            if _normalize(character.name) == target
        ]
        if len(matches) == 1:
            return ResolutionResult(
                canonical_id=matches[0].id,
                status="MATCHED",
                confidence=1.0,
                reason="Exact normalized name match.",
            )
        if len(matches) > 1:
            return ResolutionResult(
                status="AMBIGUOUS",
                confidence=1.0,
                alternatives=[character.id for character in matches],
                reason="Multiple canonical characters match the name.",
            )
        return ResolutionResult(
            status="UNRESOLVED",
            confidence=0.0,
            reason="No canonical character matches.",
        )

    def resolve_location(self, name: str) -> ResolutionResult:
        """Resolve a story location name to a canonical location."""
        target = _normalize(name)
        matches = [
            location for location in self._context.locations if _normalize(location.name) == target
        ]
        if len(matches) == 1:
            return ResolutionResult(
                canonical_id=matches[0].id,
                status="MATCHED",
                confidence=1.0,
                reason="Exact normalized name match.",
            )
        if len(matches) > 1:
            return ResolutionResult(
                status="AMBIGUOUS",
                confidence=1.0,
                alternatives=[location.id for location in matches],
                reason="Multiple canonical locations match the name.",
            )
        return ResolutionResult(
            status="UNRESOLVED",
            confidence=0.0,
            reason="No canonical location matches.",
        )

    def resolve_object(self, name: str) -> ResolutionResult:
        """Resolve a story object name to a canonical story object."""
        target = _normalize(name)
        matches = [obj for obj in self._context.objects if _normalize(obj.name) == target]
        if len(matches) == 1:
            return ResolutionResult(
                canonical_id=matches[0].id,
                status="MATCHED",
                confidence=1.0,
                reason="Exact normalized name match.",
            )
        if len(matches) > 1:
            return ResolutionResult(
                status="AMBIGUOUS",
                confidence=1.0,
                alternatives=[obj.id for obj in matches],
                reason="Multiple canonical objects match the name.",
            )
        return ResolutionResult(
            status="UNRESOLVED",
            confidence=0.0,
            reason="No canonical object matches.",
        )
