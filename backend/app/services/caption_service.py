"""Caption/subtitle domain service."""

from sqlalchemy.orm import Session

from app.models import Caption, Narration, Scene, Shot, VideoAssembly
from app.schemas.caption import CaptionCreate, CaptionStyle, CaptionUpdate
from app.services.video_assembly_service import VideoAssemblyService


class CaptionError(Exception):
    """Raised when caption validation fails."""


class CaptionNotFoundError(Exception):
    """Raised when a caption cannot be found."""


class CaptionService:
    """Manages timed captions for video assemblies."""

    DEFAULT_STYLE = CaptionStyle()

    def __init__(self, db: Session) -> None:
        self._db = db

    def _assert_assembly(self, series_id: str, assembly_id: str) -> VideoAssembly:
        assembly_service = VideoAssemblyService(self._db)
        return assembly_service.get(series_id, assembly_id)

    def _assert_narration_in_episode(
        self, series_id: str, episode_id: str, narration_id: str | None
    ) -> None:
        if narration_id is None:
            return
        narration = self._db.get(Narration, narration_id)
        if (
            not narration
            or str(narration.series_id) != series_id
            or str(narration.episode_id) != episode_id
        ):
            raise CaptionError("Narration does not belong to this series/episode.")

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
            raise CaptionError("Scene does not belong to this episode/series.")

    def _assert_shot_in_episode(self, series_id: str, episode_id: str, shot_id: str | None) -> None:
        if shot_id is None:
            return
        shot = self._db.get(Shot, shot_id)
        if (
            not shot
            or str(shot.scene.episode_id) != episode_id
            or str(shot.scene.episode.series_id) != series_id
        ):
            raise CaptionError("Shot does not belong to this episode/series.")

    def _validate_caption(
        self,
        assembly: VideoAssembly,
        data: CaptionCreate | CaptionUpdate,
        existing: Caption | None = None,
    ) -> None:
        start = data.start_time_seconds
        end = data.end_time_seconds
        if start is not None and end is not None and end <= start:
            raise CaptionError("end_time_seconds must be greater than start_time_seconds.")
        if getattr(data, "text", None) is not None:
            text = data.text.strip()
            if not text:
                raise CaptionError("Caption text must not be empty or whitespace only.")
            style = data.style or self.DEFAULT_STYLE
            self._wrap_text(text, style)
        if start is not None and start < 0:
            raise CaptionError("start_time_seconds must be non-negative.")
        if end is not None and end < 0:
            raise CaptionError("end_time_seconds must be non-negative.")
        if (
            end is not None
            and assembly.duration_seconds is not None
            and end > assembly.duration_seconds
        ):
            raise CaptionError("Caption end time exceeds the assembly duration.")

    def _wrap_text(self, text: str, style: CaptionStyle) -> str:
        """Word-wrap caption text to ASS newlines."""
        max_chars = style.max_chars_per_line
        max_lines = style.max_lines
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            if len(word) > max_chars:
                if current:
                    lines.append(current)
                    current = ""
                for i in range(0, len(word), max_chars):
                    chunk = word[i : i + max_chars]
                    if len(lines) >= max_lines:
                        raise CaptionError("Caption exceeds maximum allowed lines.")
                    lines.append(chunk)
                continue
            candidate = f"{current} {word}".strip() if current else word
            if len(candidate) > max_chars:
                if current:
                    if len(lines) >= max_lines:
                        raise CaptionError("Caption exceeds maximum allowed lines.")
                    lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            if len(lines) >= max_lines:
                raise CaptionError("Caption exceeds maximum allowed lines.")
            lines.append(current)
        if not lines:
            raise CaptionError("Caption text is empty.")
        return r"\N".join(lines)

    def create(self, series_id: str, data: CaptionCreate) -> Caption:
        """Create a caption for an assembly."""
        assembly = self._assert_assembly(series_id, str(data.assembly_id))
        self._validate_caption(assembly, data)
        self._assert_narration_in_episode(
            series_id,
            str(assembly.episode_id),
            str(data.narration_id) if data.narration_id else None,
        )
        self._assert_scene_in_episode(
            series_id, str(assembly.episode_id), str(data.scene_id) if data.scene_id else None
        )
        self._assert_shot_in_episode(
            series_id, str(assembly.episode_id), str(data.shot_id) if data.shot_id else None
        )

        caption = Caption(
            series_id=series_id,
            episode_id=str(assembly.episode_id),
            assembly_id=str(data.assembly_id),
            scene_id=str(data.scene_id) if data.scene_id else None,
            shot_id=str(data.shot_id) if data.shot_id else None,
            narration_id=str(data.narration_id) if data.narration_id else None,
            text=data.text,
            start_time_seconds=data.start_time_seconds,
            end_time_seconds=data.end_time_seconds,
            sequence_order=data.sequence_order,
            style=data.style.model_dump() if data.style else None,
            locale=data.locale,
            caption_metadata=data.caption_metadata,
        )
        self._db.add(caption)
        self._db.flush()
        self._db.refresh(caption)
        return caption

    def list_for_assembly(self, series_id: str, assembly_id: str) -> list[Caption]:
        """List captions for an assembly in deterministic order."""
        self._assert_assembly(series_id, assembly_id)
        return (
            self._db.query(Caption)
            .filter_by(assembly_id=assembly_id)
            .order_by(Caption.start_time_seconds, Caption.end_time_seconds, Caption.sequence_order)
            .all()
        )

    def get(self, series_id: str, caption_id: str) -> Caption:
        """Retrieve a caption."""
        caption = self._db.get(Caption, caption_id)
        if not caption or caption.series_id != series_id:
            raise CaptionNotFoundError("Caption not found.")
        return caption

    def update(self, series_id: str, caption_id: str, data: CaptionUpdate) -> Caption:
        """Update a caption."""
        caption = self.get(series_id, caption_id)
        assembly = self._assert_assembly(series_id, caption.assembly_id)
        self._validate_caption(assembly, data, caption)

        narration_id = data.narration_id
        scene_id = data.scene_id
        shot_id = data.shot_id

        if narration_id is not None:
            self._assert_narration_in_episode(
                series_id, str(assembly.episode_id), str(narration_id) if narration_id else None
            )
        if scene_id is not None:
            self._assert_scene_in_episode(
                series_id, str(assembly.episode_id), str(scene_id) if scene_id else None
            )
        if shot_id is not None:
            self._assert_shot_in_episode(
                series_id, str(assembly.episode_id), str(shot_id) if shot_id else None
            )

        payload = data.model_dump(exclude_unset=True, mode="json")
        for key, value in payload.items():
            if value is not None or key in {
                "scene_id",
                "shot_id",
                "narration_id",
                "style",
                "caption_metadata",
                "locale",
            }:
                setattr(caption, key, value)
        self._db.flush()
        self._db.refresh(caption)
        return caption

    def remove(self, series_id: str, caption_id: str) -> None:
        """Delete a caption."""
        caption = self.get(series_id, caption_id)
        self._db.delete(caption)
        self._db.flush()

    def wrap_text(self, text: str, style_dict: dict | None = None) -> str:
        """Public helper to wrap text with a stored or default style."""
        style = CaptionStyle(**style_dict) if style_dict else self.DEFAULT_STYLE
        return self._wrap_text(text, style)

    def default_style(self) -> CaptionStyle:
        return self.DEFAULT_STYLE
