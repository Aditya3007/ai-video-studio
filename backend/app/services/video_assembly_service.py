"""Video assembly and timeline domain service."""

from sqlalchemy.orm import Session

from app.models import (
    AssemblyItem,
    Asset,
    AudioCue,
    Episode,
    Narration,
    Scene,
    Series,
    Shot,
    VideoAssembly,
)
from app.models.enums import (
    AssemblyItemType,
    AssemblyTrack,
    AssetType,
)
from app.schemas.video_assembly import (
    AssemblyItemCreate,
    AssemblyItemUpdate,
    VideoAssemblyCreate,
    VideoAssemblyUpdate,
)


class VideoAssemblyError(Exception):
    """Raised when video assembly validation fails."""


class VideoAssemblyNotFoundError(Exception):
    """Raised when a video assembly cannot be found."""


class AssemblyItemError(Exception):
    """Raised when an assembly item validation fails."""


class AssemblyItemNotFoundError(Exception):
    """Raised when an assembly item cannot be found."""


class VideoAssemblyService:
    """Manages canonical video assemblies and their timeline items."""

    _ITEM_TRACK_MAP = {
        AssemblyItemType.VIDEO.value: AssemblyTrack.VIDEO.value,
        AssemblyItemType.NARRATION.value: AssemblyTrack.DIALOGUE.value,
        AssemblyItemType.MUSIC.value: AssemblyTrack.MUSIC.value,
        AssemblyItemType.SOUND_EFFECT.value: AssemblyTrack.SFX.value,
    }
    _ITEM_ASSET_TYPE = {
        AssemblyItemType.VIDEO.value: AssetType.VIDEO.value,
        AssemblyItemType.NARRATION.value: AssetType.AUDIO.value,
        AssemblyItemType.MUSIC.value: AssetType.AUDIO.value,
        AssemblyItemType.SOUND_EFFECT.value: AssetType.AUDIO.value,
    }

    def __init__(self, db: Session) -> None:
        self._db = db

    def _assert_series(self, series_id: str) -> Series:
        series = self._db.get(Series, series_id)
        if not series:
            raise VideoAssemblyError("Series not found.")
        return series

    def _assert_episode_in_series(self, series_id: str, episode_id: str) -> None:
        episode = self._db.get(Episode, episode_id)
        if not episode or str(episode.series_id) != series_id:
            raise VideoAssemblyError("Episode does not belong to this series.")

    def _assert_assembly(self, series_id: str, assembly_id: str) -> VideoAssembly:
        assembly = self._db.get(VideoAssembly, assembly_id)
        if not assembly or assembly.series_id != series_id:
            raise VideoAssemblyNotFoundError("Video assembly not found.")
        return assembly

    def _assert_scene_in_episode(
        self, series_id: str, episode_id: str, scene_id: str | None
    ) -> None:
        if scene_id is None:
            return
        scene = self._db.get(Scene, scene_id)
        if (
            not scene
            or str(scene.episode_id) != episode_id
            or str(scene.episode.series_id) != series_id
        ):
            raise AssemblyItemError("Scene does not belong to this episode/series.")

    def _assert_shot_in_episode(self, series_id: str, episode_id: str, shot_id: str | None) -> None:
        if shot_id is None:
            return
        shot = self._db.get(Shot, shot_id)
        if (
            not shot
            or str(shot.scene.episode_id) != episode_id
            or str(shot.scene.episode.series_id) != series_id
        ):
            raise AssemblyItemError("Shot does not belong to this episode/series.")

    def _assert_asset_in_series(self, series_id: str, asset_id: str, expected_type: str) -> None:
        asset = self._db.get(Asset, asset_id)
        if not asset or asset.series_id != series_id:
            raise AssemblyItemError("Asset does not belong to this series.")
        if asset.asset_type != expected_type:
            raise AssemblyItemError(f"Asset must be of type {expected_type}.")

    def _assert_narration_in_episode(
        self, series_id: str, episode_id: str, narration_id: str
    ) -> None:
        narration = self._db.get(Narration, narration_id)
        if (
            not narration
            or str(narration.series_id) != series_id
            or str(narration.episode_id) != episode_id
        ):
            raise AssemblyItemError("Narration does not belong to this episode/series.")

    def _assert_audio_cue_in_episode(
        self, series_id: str, episode_id: str, audio_cue_id: str
    ) -> None:
        cue = self._db.get(AudioCue, audio_cue_id)
        if not cue or str(cue.series_id) != series_id or str(cue.episode_id) != episode_id:
            raise AssemblyItemError("AudioCue does not belong to this episode/series.")

    def _validate_item_timing(self, data: AssemblyItemCreate | AssemblyItemUpdate) -> None:
        if data.start_time_seconds is not None and data.start_time_seconds < 0:
            raise AssemblyItemError("Start time must not be negative.")
        if data.duration_seconds is not None and data.duration_seconds <= 0:
            raise AssemblyItemError("Duration must be positive.")

    def _validate_item_against_assembly(
        self,
        data: AssemblyItemCreate,
        assembly: VideoAssembly,
    ) -> None:
        self._validate_item_timing(data)
        self._assert_scene_in_episode(
            assembly.series_id, assembly.episode_id, str(data.scene_id) if data.scene_id else None
        )
        self._assert_shot_in_episode(
            assembly.series_id, assembly.episode_id, str(data.shot_id) if data.shot_id else None
        )

        item_type = data.item_type.value
        expected_track = self._ITEM_TRACK_MAP[item_type]
        if data.track.value != expected_track:
            raise AssemblyItemError(f"Track {data.track.value} is not valid for {item_type}.")

        expected_asset_type = self._ITEM_ASSET_TYPE[item_type]
        if data.asset_id is None:
            raise AssemblyItemError("An Asset is required for each timeline item.")
        self._assert_asset_in_series(
            assembly.series_id,
            str(data.asset_id),
            expected_asset_type,
        )

        if item_type == AssemblyItemType.VIDEO.value:
            if data.shot_id is None:
                raise AssemblyItemError("Video items require a shot reference.")
            if data.scene_id is None:
                raise AssemblyItemError("Video items require a scene reference.")

        if item_type == AssemblyItemType.NARRATION.value:
            if data.narration_id is None:
                raise AssemblyItemError("Narration items require a narration reference.")
            self._assert_narration_in_episode(
                assembly.series_id,
                assembly.episode_id,
                str(data.narration_id),
            )

        if item_type in (AssemblyItemType.MUSIC.value, AssemblyItemType.SOUND_EFFECT.value):
            if data.audio_cue_id is None:
                raise AssemblyItemError("Music/SFX items require an AudioCue reference.")
            self._assert_audio_cue_in_episode(
                assembly.series_id,
                assembly.episode_id,
                str(data.audio_cue_id),
            )

    def _validate_update_against_assembly(
        self,
        item: AssemblyItem,
        data: AssemblyItemUpdate,
        assembly: VideoAssembly,
    ) -> None:
        self._validate_item_timing(data)

        item_type = data.item_type.value if data.item_type else item.item_type
        track = data.track.value if data.track else item.track
        expected_track = self._ITEM_TRACK_MAP[item_type]
        if track != expected_track:
            raise AssemblyItemError(f"Track {track} is not valid for {item_type}.")

        scene_id = str(data.scene_id) if data.scene_id is not None else item.scene_id
        shot_id = str(data.shot_id) if data.shot_id is not None else item.shot_id
        self._assert_scene_in_episode(assembly.series_id, assembly.episode_id, scene_id)
        self._assert_shot_in_episode(assembly.series_id, assembly.episode_id, shot_id)

        expected_asset_type = self._ITEM_ASSET_TYPE[item_type]
        asset_id = str(data.asset_id) if data.asset_id is not None else item.asset_id
        if asset_id is None:
            raise AssemblyItemError("An Asset is required for each timeline item.")
        self._assert_asset_in_series(assembly.series_id, asset_id, expected_asset_type)

        if item_type == AssemblyItemType.VIDEO.value:
            if shot_id is None or scene_id is None:
                raise AssemblyItemError("Video items require scene and shot references.")

        if item_type == AssemblyItemType.NARRATION.value:
            narration_id = (
                str(data.narration_id) if data.narration_id is not None else item.narration_id
            )
            if narration_id is None:
                raise AssemblyItemError("Narration items require a narration reference.")
            self._assert_narration_in_episode(assembly.series_id, assembly.episode_id, narration_id)

        if item_type in (AssemblyItemType.MUSIC.value, AssemblyItemType.SOUND_EFFECT.value):
            audio_cue_id = (
                str(data.audio_cue_id) if data.audio_cue_id is not None else item.audio_cue_id
            )
            if audio_cue_id is None:
                raise AssemblyItemError("Music/SFX items require an AudioCue reference.")
            self._assert_audio_cue_in_episode(assembly.series_id, assembly.episode_id, audio_cue_id)

    def create(self, series_id: str, data: VideoAssemblyCreate) -> VideoAssembly:
        """Create a new video assembly for an episode."""
        self._assert_series(series_id)
        self._assert_episode_in_series(series_id, str(data.episode_id))

        assembly = VideoAssembly(
            series_id=series_id,
            episode_id=str(data.episode_id),
            status=data.status.value,
            output_config=data.output_config,
            duration_seconds=data.duration_seconds,
            assembly_metadata=data.assembly_metadata,
        )
        self._db.add(assembly)
        self._db.flush()
        self._db.refresh(assembly)
        return assembly

    def get(self, series_id: str, assembly_id: str) -> VideoAssembly:
        """Retrieve a video assembly, ensuring series ownership."""
        return self._assert_assembly(series_id, assembly_id)

    def get_by_episode(self, series_id: str, episode_id: str) -> VideoAssembly | None:
        """Return the assembly for an episode if it exists."""
        return (
            self._db.query(VideoAssembly)
            .filter_by(series_id=series_id, episode_id=episode_id)
            .first()
        )

    def update(
        self,
        series_id: str,
        assembly_id: str,
        data: VideoAssemblyUpdate,
    ) -> VideoAssembly:
        """Update an assembly's metadata and output configuration."""
        assembly = self._assert_assembly(series_id, assembly_id)
        payload = data.model_dump(exclude_unset=True, mode="json")
        for key, value in payload.items():
            setattr(assembly, key, value)
        self._db.flush()
        self._db.refresh(assembly)
        return assembly

    def add_item(
        self,
        series_id: str,
        assembly_id: str,
        data: AssemblyItemCreate,
    ) -> AssemblyItem:
        """Add a validated timeline item to an assembly."""
        assembly = self._assert_assembly(series_id, assembly_id)
        self._validate_item_against_assembly(data, assembly)

        item = AssemblyItem(
            assembly_id=assembly_id,
            series_id=series_id,
            episode_id=assembly.episode_id,
            scene_id=str(data.scene_id) if data.scene_id else None,
            shot_id=str(data.shot_id) if data.shot_id else None,
            item_type=data.item_type.value,
            track=data.track.value,
            sequence_order=data.sequence_order,
            start_time_seconds=data.start_time_seconds,
            duration_seconds=data.duration_seconds,
            asset_id=str(data.asset_id) if data.asset_id else None,
            narration_id=str(data.narration_id) if data.narration_id else None,
            audio_cue_id=str(data.audio_cue_id) if data.audio_cue_id else None,
            item_metadata=data.item_metadata,
        )
        self._db.add(item)
        self._db.flush()
        self._db.refresh(item)
        return item

    def list_items(self, series_id: str, assembly_id: str) -> list[AssemblyItem]:
        """List timeline items for an assembly in deterministic order."""
        assembly = self._assert_assembly(series_id, assembly_id)
        return (
            self._db.query(AssemblyItem)
            .filter_by(assembly_id=assembly.id)
            .order_by(
                AssemblyItem.track, AssemblyItem.sequence_order, AssemblyItem.start_time_seconds
            )
            .all()
        )

    def get_item(
        self,
        series_id: str,
        assembly_id: str,
        item_id: str,
    ) -> AssemblyItem:
        """Retrieve a timeline item, ensuring series ownership."""
        item = self._db.get(AssemblyItem, item_id)
        if not item or item.assembly_id != assembly_id or item.series_id != series_id:
            raise AssemblyItemNotFoundError("Assembly item not found.")
        return item

    def update_item(
        self,
        series_id: str,
        assembly_id: str,
        item_id: str,
        data: AssemblyItemUpdate,
    ) -> AssemblyItem:
        """Update a timeline item."""
        assembly = self._assert_assembly(series_id, assembly_id)
        item = self.get_item(series_id, assembly_id, item_id)
        self._validate_update_against_assembly(item, data, assembly)

        payload = data.model_dump(exclude_unset=True, mode="json")
        for key, value in payload.items():
            if value is not None or key in {
                "scene_id",
                "shot_id",
                "narration_id",
                "audio_cue_id",
                "asset_id",
                "item_metadata",
            }:
                setattr(item, key, value)
        self._db.flush()
        self._db.refresh(item)
        return item

    def remove_item(
        self,
        series_id: str,
        assembly_id: str,
        item_id: str,
    ) -> None:
        """Remove a timeline item from an assembly."""
        item = self.get_item(series_id, assembly_id, item_id)
        self._db.delete(item)
        self._db.flush()
