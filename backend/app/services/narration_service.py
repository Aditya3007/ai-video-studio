"""Narration/dialogue domain service."""

from sqlalchemy.orm import Session

from app.models import (
    Asset,
    Character,
    Episode,
    Narration,
    Scene,
    Series,
    Shot,
    Voice,
)
from app.schemas.narration import NarrationCreate


class NarrationError(Exception):
    """Raised when narration validation fails."""


class NarrationNotFoundError(Exception):
    """Raised when a narration cannot be found."""


class NarrationService:
    """Manages narration and dialogue items within a series."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _assert_series(self, series_id: str) -> Series:
        series = self._db.get(Series, series_id)
        if not series:
            raise NarrationError("Series not found.")
        return series

    def _validate_episode(self, series_id: str, episode_id: str) -> None:
        episode = self._db.get(Episode, episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise NarrationError("Episode does not belong to this series.")

    def _validate_scene(self, series_id: str, scene_id: str | None) -> None:
        if scene_id is None:
            return
        scene = self._db.get(Scene, scene_id)
        if not scene or str(scene.episode.series_id) != series_id:
            raise NarrationError("Scene does not belong to this series.")

    def _validate_shot(self, series_id: str, shot_id: str | None) -> None:
        if shot_id is None:
            return
        shot = self._db.get(Shot, shot_id)
        if not shot or str(shot.scene.episode.series_id) != series_id:
            raise NarrationError("Shot does not belong to this series.")

    def _validate_voice(self, series_id: str, voice_id: str | None) -> None:
        if voice_id is None:
            return
        voice = self._db.get(Voice, voice_id)
        if not voice or voice.series_id != series_id:
            raise NarrationError("Voice does not belong to this series.")

    def _validate_character(self, series_id: str, character_id: str | None) -> None:
        if character_id is None:
            return
        character = self._db.get(Character, character_id)
        if not character or str(character.series_id) != series_id:
            raise NarrationError("Character does not belong to this series.")

    def _validate_asset(self, series_id: str, asset_id: str | None) -> None:
        if asset_id is None:
            return
        asset = self._db.get(Asset, asset_id)
        if not asset or asset.series_id != series_id:
            raise NarrationError("Asset does not belong to this series.")

    def create(self, series_id: str, data: NarrationCreate) -> Narration:
        """Create a new narration item within a series."""
        self._assert_series(series_id)
        self._validate_episode(series_id, str(data.episode_id))
        self._validate_scene(series_id, str(data.scene_id) if data.scene_id else None)
        self._validate_shot(series_id, str(data.shot_id) if data.shot_id else None)
        self._validate_voice(series_id, str(data.voice_id) if data.voice_id else None)
        self._validate_character(series_id, str(data.character_id) if data.character_id else None)

        self._validate_asset(
            series_id, str(data.generated_asset_id) if data.generated_asset_id else None
        )

        narration = Narration(
            series_id=series_id,
            episode_id=str(data.episode_id),
            scene_id=str(data.scene_id) if data.scene_id else None,
            shot_id=str(data.shot_id) if data.shot_id else None,
            voice_id=str(data.voice_id) if data.voice_id else None,
            character_id=str(data.character_id) if data.character_id else None,
            source_text=data.source_text,
            narration_type=data.narration_type.value,
            status=data.status.value,
            generated_asset_id=str(data.generated_asset_id) if data.generated_asset_id else None,
            duration_seconds=data.duration_seconds,
            audio_metadata=data.audio_metadata,
        )
        self._db.add(narration)
        self._db.flush()
        self._db.refresh(narration)
        return narration

    def get(self, series_id: str, narration_id: str) -> Narration:
        """Retrieve a narration by ID, ensuring series ownership."""
        narration = self._db.get(Narration, narration_id)
        if not narration or narration.series_id != series_id:
            raise NarrationNotFoundError("Narration not found.")
        return narration

    def list(self, series_id: str) -> list[Narration]:
        """List narrations within a series."""
        return self._db.query(Narration).filter_by(series_id=series_id).all()
