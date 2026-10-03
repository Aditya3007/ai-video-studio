"""Provider-neutral generated video clip validation."""

from app.media_generation.video.errors import VideoValidationError
from app.media_generation.video.provider import (
    VideoGenerationRequest,
    VideoGenerationResult,
    VideoReference,
)


class VideoClipValidator:
    """Validate a generated video result against provider-neutral constraints."""

    DURATION_TOLERANCE = 1.0  # seconds

    @classmethod
    def validate(
        cls,
        request: VideoGenerationRequest,
        result: VideoGenerationResult,
    ) -> dict:
        """Validate result metadata and return a validation summary."""
        if not result.videos:
            raise VideoValidationError("No video output returned.")

        checks = []
        for idx, video in enumerate(result.videos):
            checks.append(cls._validate_reference(request, video, idx))

        return {"valid": True, "checks": checks}

    @classmethod
    def _validate_reference(
        cls,
        request: VideoGenerationRequest,
        video: VideoReference,
        index: int,
    ) -> dict:
        prefix = f"video[{index}]"
        errors = []

        if not video.uri or not video.uri.strip():
            errors.append(f"{prefix}: missing output reference.")

        if not video.content_type or not video.content_type.startswith("video/"):
            errors.append(f"{prefix}: invalid content type '{video.content_type}'.")

        if video.width <= 0 or video.height <= 0:
            errors.append(f"{prefix}: invalid dimensions {video.width}x{video.height}.")

        if video.duration <= 0:
            errors.append(f"{prefix}: invalid duration {video.duration}.")

        if request.aspect_ratio:
            cls._validate_aspect_ratio(request, video, errors, prefix)

        if request.width is not None and video.width != request.width:
            errors.append(
                f"{prefix}: width {video.width} does not match requested {request.width}."
            )
        if request.height is not None and video.height != request.height:
            errors.append(
                f"{prefix}: height {video.height} does not match requested {request.height}."
            )

        if request.duration is not None:
            if abs(video.duration - request.duration) > cls.DURATION_TOLERANCE:
                errors.append(
                    f"{prefix}: duration {video.duration} deviates from "
                    f"requested {request.duration}."
                )

        if errors:
            raise VideoValidationError("; ".join(errors))

        return {
            "index": index,
            "content_type": video.content_type,
            "width": video.width,
            "height": video.height,
            "duration": video.duration,
        }

    @classmethod
    def _validate_aspect_ratio(
        cls,
        request: VideoGenerationRequest,
        video: VideoReference,
        errors: list[str],
        prefix: str,
    ) -> None:
        ratio = request.aspect_ratio
        if not ratio or ":" not in ratio:
            return
        try:
            req_w, req_h = ratio.split(":")
            req_w_int = int(req_w)
            req_h_int = int(req_h)
        except (ValueError, AttributeError):
            return
        if req_w_int <= 0 or req_h_int <= 0:
            return
        if video.width * req_h_int != video.height * req_w_int:
            errors.append(
                f"{prefix}: aspect ratio {video.width}:{video.height} "
                f"does not match requested {ratio}."
            )
