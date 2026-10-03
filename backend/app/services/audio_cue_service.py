"""Audio cue domain service for music and sound effects."""

from sqlalchemy.orm import Session

from app.models import Asset, AudioCue, Episode, Scene, Series, Shot
from app.schemas.audio_cue import AudioCueCreate


class AudioCueError(Exception):
    """Raised when audio cue validation fails."""


class AudioCueNotFoundError(Exception):
    """Raised when an audio cue cannot be found."""


class AudioCueService:
    """Manages music and sound-effect cues within a series."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _assert_series(self, series_id: str) -> Series:
        series = self._db.get(Series, series_id)
        if not series:
            raise AudioCueError("Series not found.")
        return series

    def _validate_episode(self, series_id: str, episode_id: str) -> None:
        episode = self._db.get(Episode, episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise AudioCueError("Episode does not belong to this series.")

    def _validate_scene(self, series_id: str, scene_id: str | None) -> None:
        if scene_id is None:
            return
        scene = self._db.get(Scene, scene_id)
        if not scene or str(scene.episode.series_id) != series_id:
            raise AudioCueError("Scene does not belong to this series.")

    def _validate_shot(self, series_id: str, shot_id: str | None) -> None:
        if shot_id is None:
            return
        shot = self._db.get(Shot, shot_id)
        if not shot or str(shot.scene.episode.series_id) != series_id:
            raise AudioCueError("Shot does not belong to this series.")

    def _validate_asset(self, series_id: str, asset_id: str | None) -> None:
        if asset_id is None:
            return
        asset = self._db.get(Asset, asset_id)
        if not asset or asset.series_id != series_id:
            raise AudioCueError("Asset does not belong to this series.")

    def create(self, series_id: str, data: AudioCueCreate) -> AudioCue:
        """Create a new audio cue within a series."""
        self._assert_series(series_id)
        self._validate_episode(series_id, str(data.episode_id))
        self._validate_scene(series_id, str(data.scene_id) if data.scene_id else None)
        self._validate_shot(series_id, str(data.shot_id) if data.shot_id else None)
        self._validate_asset(
            series_id, str(data.generated_asset_id) if data.generated_asset_id else None
        )

        cue = AudioCue(
            series_id=series_id,
            episode_id=str(data.episode_id),
            scene_id=str(data.scene_id) if data.scene_id else None,
            shot_id=str(data.shot_id) if data.shot_id else None,
            name=data.name,
            description=data.description,
            audio_type=data.audio_type.value,
            status=data.status.value,
            prompt=data.prompt,
            duration_seconds=data.duration_seconds,
            start_time_seconds=data.start_time_seconds,
            end_time_seconds=data.end_time_seconds,
            volume=data.volume,
            loop=data.loop,
            fade_in=data.fade_in,
            fade_out=data.fade_out,
            generated_asset_id=str(data.generated_asset_id) if data.generated_asset_id else None,
            audio_metadata=data.audio_metadata,
        )
        self._db.add(cue)
        self._db.flush()
        self._db.refresh(cue)
        return cue

    def get(self, series_id: str, cue_id: str) -> AudioCue:
        """Retrieve an audio cue by ID, ensuring series ownership."""
        cue = self._db.get(AudioCue, cue_id)
        if not cue or cue.series_id != series_id:
            raise AudioCueNotFoundError("Audio cue not found.")
        return cue

    def list(self, series_id: str) -> list[AudioCue]:
        """List audio cues within a series."""
        return self._db.query(AudioCue).filter_by(series_id=series_id).all()
