"""Prompt construction for story analysis and topic expansion."""

# ruff: noqa: E501

import json

from app.models.story import Story, StoryVersion
from app.schemas.universe import UniverseContextResponse

_SYSTEM_PROMPT = """You are a story analysis assistant for an AI video production system.

Your job is to transform user-supplied story material into a structured, provider-neutral JSON representation that will later be used for screenplay generation.

Rules:
- Do not write a screenplay or shot list.
- Preserve dialogue text exactly when it is present in the source.
- Reuse existing canonical characters, locations, and objects from the universe context when they match entities in the story. Do not invent canonical IDs; simply use the names as they appear.
- For topics, expand the premise into a structured story concept but do not generate a full script.
- Output only valid JSON matching the requested schema.
"""


def build_analysis_prompt(
    story: Story,
    story_version: StoryVersion,
    universe_context: UniverseContextResponse,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the analyzer."""
    universe = json.dumps(universe_context.model_dump(mode="json"), default=str)
    story_info = {
        "title": story.title,
        "description": story.description,
        "source_type": story.source_type,
        "source_content": story_version.content,
        "language": story.language,
    }

    user_prompt = f"""Analyze the following {story.source_type.lower().replace('_', ' ')} and produce a structured JSON story analysis.

Story:
```json
{json.dumps(story_info, indent=2)}
```

Universe context (canonical characters, locations, objects, world, bibles):
```json
{universe}
```

Return a JSON object with the following top-level fields:
- status: one of PENDING, ANALYZING, COMPLETED, FAILED, REVIEW_REQUIRED
- metadata: {{title, logline, premise, theme, genre, tone, target_audience, language}}
- narrative: {{acts, beginning, inciting_incident, rising_action, midpoint, climax, resolution, plot_beats}}
- characters: list of {{name, aliases, role, description, personality, motivations, goals, conflicts, relationships, character_arc, appearance_notes, dialogue_style}}
- locations: list of {{name, description, significance, atmosphere, time_context}}
- objects: list of {{name, description, significance, ownership_context}}
- events: list of {{id, sequence, summary, description, involved_characters, location, cause, consequence, emotional_significance, time_context}}
- dialogue: list of {{speaker, text, sequence, context, associated_event_id}}
- beats: list of {{id, type, summary, sequence, involved_characters, event_ids, emotional_state, importance}}
- source_refs: list of {{source_version_id, chapter, paragraph, start_offset, end_offset, excerpt}}
- warnings: list of strings
- unresolved_entities: list of objects

Do not include story_id or story_version_id; those will be filled by the application.
"""

    return _SYSTEM_PROMPT, user_prompt
