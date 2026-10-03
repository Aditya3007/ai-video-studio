"""Voice domain service."""

from sqlalchemy.orm import Session

from app.models import Character, Series, Voice
from app.schemas.voice import VoiceCreate


class VoiceError(Exception):
    """Raised when voice validation fails."""


class VoiceNotFoundError(Exception):
    """Raised when a voice cannot be found."""


class VoiceService:
    """Manages voice identities within a series."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _assert_series(self, series_id: str) -> Series:
        series = self._db.get(Series, series_id)
        if not series:
            raise VoiceError("Series not found.")
        return series

    def _validate_character(self, series_id: str, character_id: str | None) -> None:
        if character_id is None:
            return
        character = self._db.get(Character, character_id)
        if not character or str(character.series_id) != series_id:
            raise VoiceError("Character does not belong to this series.")

    def create(self, series_id: str, data: VoiceCreate) -> Voice:
        """Create a new voice within a series."""
        self._assert_series(series_id)
        self._validate_character(series_id, str(data.character_id) if data.character_id else None)

        voice = Voice(
            series_id=series_id,
            name=data.name,
            description=data.description,
            character_id=str(data.character_id) if data.character_id else None,
            voice_metadata=data.voice_metadata,
        )
        self._db.add(voice)
        self._db.flush()
        self._db.refresh(voice)
        return voice

    def get(self, series_id: str, voice_id: str) -> Voice:
        """Retrieve a voice by ID, ensuring series ownership."""
        voice = self._db.get(Voice, voice_id)
        if not voice or voice.series_id != series_id:
            raise VoiceNotFoundError("Voice not found.")
        return voice

    def list(self, series_id: str) -> list[Voice]:
        """List voices within a series."""
        return self._db.query(Voice).filter_by(series_id=series_id).all()
