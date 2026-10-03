"""Central API router for versioned endpoints."""

from fastapi import APIRouter

from app.api.routes import (
    ai_qa,
    assets,
    audio_cues,
    budget,
    captions,
    character_versions,
    characters,
    continuity,
    costs,
    episodes,
    image_generation_jobs,
    image_to_video,
    issue_resolution,
    location_versions,
    locations,
    narrations,
    objects,
    publish,
    publishing,
    qa_workflow,
    scenes,
    series,
    shots,
    storage,
    story,
    story_analysis,
    storyboards,
    studio,
    unit_economics,
    video_assemblies,
    video_generation_jobs,
    voices,
    worlds,
)

api_router = APIRouter()

api_router.include_router(series.router)
api_router.include_router(worlds.router)
api_router.include_router(characters.router)
api_router.include_router(character_versions.router)
api_router.include_router(locations.router)
api_router.include_router(location_versions.router)
api_router.include_router(objects.router)
api_router.include_router(assets.router)
api_router.include_router(continuity.router)
api_router.include_router(budget.router)
api_router.include_router(costs.router)
api_router.include_router(unit_economics.router)
api_router.include_router(ai_qa.router)
api_router.include_router(qa_workflow.router)
api_router.include_router(issue_resolution.router)
api_router.include_router(studio.router)
api_router.include_router(episodes.router)
api_router.include_router(scenes.router)
api_router.include_router(shots.router)
api_router.include_router(storyboards.router)
api_router.include_router(image_generation_jobs.router)
api_router.include_router(image_to_video.router)
api_router.include_router(video_generation_jobs.router)
api_router.include_router(video_assemblies.router)
api_router.include_router(voices.router)
api_router.include_router(narrations.router)
api_router.include_router(audio_cues.router)
api_router.include_router(captions.router)
api_router.include_router(publish.router)
api_router.include_router(publishing.router)
api_router.include_router(story.router)
api_router.include_router(story_analysis.router)
api_router.include_router(storage.router)


@api_router.get("/health")
async def api_health() -> dict[str, str]:
    """Framework-level health endpoint for the v1 API."""
    return {"status": "healthy", "api": "v1"}
