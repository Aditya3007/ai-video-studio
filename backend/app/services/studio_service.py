"""Studio production workflow aggregation service."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AssemblyItem,
    Asset,
    Character,
    Episode,
    Location,
    Scene,
    Series,
    Shot,
    Story,
    StoryObject,
    VideoAssembly,
)
from app.models.enums import QAWorkflowStatus
from app.schemas.studio import (
    StudioEpisodeProductionResponse,
    StudioEpisodeSummary,
    StudioSceneProductionResponse,
    StudioSceneSummary,
    StudioSeriesOverviewResponse,
    StudioShotProductionResponse,
    StudioShotSummary,
    StudioVideoAssemblySummary,
)
from app.services.qa_workflow_service import QAWorkflowService


class StudioNotFoundError(Exception):
    """Raised when a requested Studio scope cannot be resolved."""


class StudioService:
    """Aggregates production state for the Studio backend API."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_series_overview(self, series_id: str) -> StudioSeriesOverviewResponse:
        series = self._db.get(Series, series_id)
        if not series:
            raise StudioNotFoundError("Series not found.")

        counts = self._series_counts(series_id)
        episodes = self._episode_summaries(series_id)

        return StudioSeriesOverviewResponse(
            series=series,
            counts=counts,
            episodes=episodes,
        )

    def get_episode_production(
        self, series_id: str, episode_id: str
    ) -> StudioEpisodeProductionResponse:
        series = self._db.get(Series, series_id)
        if not series:
            raise StudioNotFoundError("Series not found.")

        episode = self._db.execute(
            select(Episode)
            .where(Episode.id == episode_id, Episode.series_id == series_id)
            .options(
                selectinload(Episode.scenes)
                .selectinload(Scene.shots)
                .selectinload(Shot.specification),
                selectinload(Episode.story),
            )
        ).scalar_one_or_none()
        if not episode:
            raise StudioNotFoundError("Episode not found.")

        assembly = self._load_assembly_summary(series_id, episode_id)
        scenes = self._build_scene_summaries(episode.scenes, series_id)
        qa_status = self._episode_qa_status(series_id, episode_id)

        return StudioEpisodeProductionResponse(
            series_id=UUID(series_id),
            episode=episode,
            story=episode.story,
            scenes=scenes,
            assembly=assembly,
            qa_status=qa_status,
        )

    def get_scene_production(
        self, series_id: str, episode_id: str, scene_id: str
    ) -> StudioSceneProductionResponse:
        series = self._db.get(Series, series_id)
        if not series:
            raise StudioNotFoundError("Series not found.")

        episode = self._db.get(Episode, episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise StudioNotFoundError("Episode not found.")

        scene = self._db.execute(
            select(Scene)
            .where(Scene.id == scene_id, Scene.episode_id == episode_id)
            .options(selectinload(Scene.shots).selectinload(Shot.specification))
        ).scalar_one_or_none()
        if not scene:
            raise StudioNotFoundError("Scene not found.")

        assembly_item_count = self._assembly_item_count_for_scene(scene_id, series_id)
        shots = self._build_shot_summaries(scene.shots, series_id)

        return StudioSceneProductionResponse(
            series_id=UUID(series_id),
            episode_id=UUID(episode_id),
            scene=scene,
            shots=shots,
            assembly_item_count=assembly_item_count,
        )

    def get_shot_production(self, series_id: str, shot_id: str) -> StudioShotProductionResponse:
        series = self._db.get(Series, series_id)
        if not series:
            raise StudioNotFoundError("Series not found.")

        shot = self._db.execute(
            select(Shot)
            .where(Shot.id == shot_id)
            .options(selectinload(Shot.scene), selectinload(Shot.specification))
        ).scalar_one_or_none()
        if not shot:
            raise StudioNotFoundError("Shot not found.")

        scene = shot.scene
        episode = self._db.get(Episode, scene.episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise StudioNotFoundError("Shot not found in this series.")

        assets = (
            self._db.execute(
                select(Asset).where(Asset.shot_id == shot_id, Asset.series_id == series_id)
            )
            .scalars()
            .all()
        )
        assembly_item_count = self._assembly_item_count_for_shot(shot_id, series_id)
        qa_status = self._shot_qa_status(series_id, shot_id)

        return StudioShotProductionResponse(
            series_id=UUID(series_id),
            episode_id=UUID(episode.id),
            scene_id=UUID(scene.id),
            shot=shot,
            specification=shot.specification,
            assets=assets,
            assembly_item_count=assembly_item_count,
            qa_status=qa_status,
        )

    def _series_counts(self, series_id: str) -> dict[str, int]:
        return {
            "stories": self._count(Story, series_id),
            "episodes": self._count(Episode, series_id),
            "characters": self._count(Character, series_id),
            "locations": self._count(Location, series_id),
            "objects": self._count(StoryObject, series_id),
            "assets": self._count(Asset, series_id),
            "assemblies": self._count(VideoAssembly, series_id),
        }

    def _count(self, model, series_id: str) -> int:
        return (
            self._db.execute(
                select(func.count(model.id)).where(model.series_id == series_id)
            ).scalar()
            or 0
        )

    def _episode_summaries(self, series_id: str) -> list[StudioEpisodeSummary]:
        episodes = (
            self._db.execute(
                select(Episode)
                .where(Episode.series_id == series_id)
                .options(selectinload(Episode.scenes).selectinload(Scene.shots))
            )
            .scalars()
            .all()
        )
        assemblies = self._assembly_map(series_id)

        summaries: list[StudioEpisodeSummary] = []
        for episode in episodes:
            scene_count = len(episode.scenes)
            shot_count = sum(len(scene.shots) for scene in episode.scenes)
            assembly = assemblies.get(str(episode.id))
            summaries.append(
                StudioEpisodeSummary(
                    id=UUID(episode.id),
                    title=episode.title,
                    episode_number=episode.episode_number,
                    status=episode.status,
                    scene_count=scene_count,
                    shot_count=shot_count,
                    assembly_status=assembly.status if assembly else None,
                    final_asset_id=(
                        UUID(assembly.final_asset_id)
                        if assembly and assembly.final_asset_id
                        else None
                    ),
                )
            )
        return summaries

    def _assembly_map(self, series_id: str) -> dict[str, VideoAssembly]:
        assemblies = (
            self._db.execute(select(VideoAssembly).where(VideoAssembly.series_id == series_id))
            .scalars()
            .all()
        )
        return {str(a.episode_id): a for a in assemblies}

    def _load_assembly_summary(self, series_id: str, episode_id: str) -> StudioVideoAssemblySummary:
        assembly = self._db.execute(
            select(VideoAssembly).where(
                VideoAssembly.episode_id == episode_id,
                VideoAssembly.series_id == series_id,
            )
        ).scalar_one_or_none()
        if not assembly:
            return StudioVideoAssemblySummary()

        item_count = (
            self._db.execute(
                select(func.count(AssemblyItem.id)).where(
                    AssemblyItem.assembly_id == assembly.id,
                    AssemblyItem.series_id == series_id,
                )
            ).scalar()
            or 0
        )
        return StudioVideoAssemblySummary(
            id=UUID(assembly.id),
            status=assembly.status,
            duration_seconds=assembly.duration_seconds,
            final_asset_id=UUID(assembly.final_asset_id) if assembly.final_asset_id else None,
            rendered_at=assembly.rendered_at,
            item_count=item_count,
        )

    def _build_scene_summaries(
        self, scenes: list[Scene], series_id: str
    ) -> list[StudioSceneSummary]:
        shot_ids = [str(shot.id) for scene in scenes for shot in scene.shots]
        asset_counts = self._asset_counts_by_shot(shot_ids, series_id)

        return [
            StudioSceneSummary(
                id=UUID(scene.id),
                scene_number=scene.scene_number,
                title=scene.title,
                description=scene.description,
                location_id=UUID(scene.location_id) if scene.location_id else None,
                shot_count=len(scene.shots),
                shots=[
                    StudioShotSummary(
                        id=UUID(shot.id),
                        shot_number=shot.shot_number,
                        description=shot.description,
                        duration_seconds=shot.duration_seconds,
                        action=shot.action,
                        has_specification=shot.specification is not None,
                        asset_count=asset_counts.get(str(shot.id), 0),
                    )
                    for shot in scene.shots
                ],
            )
            for scene in scenes
        ]

    def _build_shot_summaries(self, shots: list[Shot], series_id: str) -> list[StudioShotSummary]:
        shot_ids = [str(shot.id) for shot in shots]
        asset_counts = self._asset_counts_by_shot(shot_ids, series_id)
        return [
            StudioShotSummary(
                id=UUID(shot.id),
                shot_number=shot.shot_number,
                description=shot.description,
                duration_seconds=shot.duration_seconds,
                action=shot.action,
                has_specification=shot.specification is not None,
                asset_count=asset_counts.get(str(shot.id), 0),
            )
            for shot in shots
        ]

    def _asset_counts_by_shot(self, shot_ids: list[str], series_id: str) -> dict[str, int]:
        if not shot_ids:
            return {}
        rows = self._db.execute(
            select(Asset.shot_id, func.count(Asset.id))
            .where(Asset.shot_id.in_(shot_ids), Asset.series_id == series_id)
            .group_by(Asset.shot_id)
        ).all()
        return {str(shot_id): count for shot_id, count in rows}

    def _assembly_item_counts_by_shot(self, shot_ids: list[str], series_id: str) -> dict[str, int]:
        if not shot_ids:
            return {}
        rows = self._db.execute(
            select(AssemblyItem.shot_id, func.count(AssemblyItem.id))
            .where(
                AssemblyItem.shot_id.in_(shot_ids),
                AssemblyItem.series_id == series_id,
            )
            .group_by(AssemblyItem.shot_id)
        ).all()
        return {str(shot_id): count for shot_id, count in rows}

    def _assembly_item_count_for_scene(self, scene_id: str, series_id: str) -> int:
        return (
            self._db.execute(
                select(func.count(AssemblyItem.id)).where(
                    AssemblyItem.scene_id == scene_id,
                    AssemblyItem.series_id == series_id,
                )
            ).scalar()
            or 0
        )

    def _assembly_item_count_for_shot(self, shot_id: str, series_id: str) -> int:
        return (
            self._db.execute(
                select(func.count(AssemblyItem.id)).where(
                    AssemblyItem.shot_id == shot_id,
                    AssemblyItem.series_id == series_id,
                )
            ).scalar()
            or 0
        )

    def _episode_qa_status(self, series_id: str, episode_id: str) -> QAWorkflowStatus:
        return (
            QAWorkflowService(self._db).evaluate_episode(series_id, episode_id, ai_modes=[]).status
        )

    def _shot_qa_status(self, series_id: str, shot_id: str) -> QAWorkflowStatus:
        return QAWorkflowService(self._db).evaluate_shot(series_id, shot_id, ai_modes=[]).status
