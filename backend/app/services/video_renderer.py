"""FFmpeg-based video assembly rendering service."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import AssemblyItem, Asset, VideoAssembly
from app.models.enums import AssemblyItemType, AssemblyStatus, AssetType
from app.services.caption_service import CaptionService
from app.services.video_assembly_service import VideoAssemblyNotFoundError, VideoAssemblyService
from app.storage import StorageBackend


class RenderResult(BaseModel):
    """Provider-neutral result of a transient render operation."""

    output_path: str
    duration_seconds: float
    width: int
    height: int
    has_video_stream: bool
    has_audio_stream: bool
    container_format: str
    size_bytes: int
    metadata: dict = Field(default_factory=dict)


class VideoRenderError(Exception):
    """Raised when video rendering fails."""


class AssemblyNotReadyError(VideoRenderError):
    """Raised when the assembly cannot be rendered in its current state."""


class MediaNotFoundError(VideoRenderError):
    """Raised when a referenced media asset is missing."""


class InvalidTimelineError(VideoRenderError):
    """Raised when the assembly timeline is invalid for rendering."""


class UnsupportedItemError(VideoRenderError):
    """Raised when an assembly item type is not supported by the renderer."""


class FFmpegNotAvailableError(VideoRenderError):
    """Raised when the FFmpeg binary is not available."""


class FFmpegExecutionError(VideoRenderError):
    """Raised when FFmpeg exits with a non-zero status."""


class RenderOutputError(VideoRenderError):
    """Raised when the produced output fails validation."""


class FFmpegCommandRunner:
    """Executes FFmpeg subprocess commands without shell interpolation."""

    def __init__(self, ffmpeg_binary: str = "ffmpeg") -> None:
        self._ffmpeg = ffmpeg_binary
        if shutil.which(ffmpeg_binary) is None:
            raise FFmpegNotAvailableError(f"FFmpeg binary not found: {ffmpeg_binary}")

    def run(self, args: list[str]) -> tuple[int, str, str]:
        """Run FFmpeg with the provided argument list and return exit code + output."""
        cmd = [self._ffmpeg, *args]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr


@runtime_checkable
class VideoRenderer(Protocol):
    """Protocol for a video assembly renderer."""

    def render(
        self,
        series_id: str,
        assembly_id: str,
        output_path: str | Path | None = None,
    ) -> RenderResult:
        """Render the assembly and return a transient result."""


class FFmpegVideoRenderer:
    """Renders a VideoAssembly to a transient MP4 using FFmpeg."""

    DEFAULT_WIDTH = 1080
    DEFAULT_HEIGHT = 1920
    DEFAULT_FPS = 30
    SAMPLE_RATE = 48000
    AUDIO_CHANNELS = 2
    SUPPORTED_ITEM_TYPES = frozenset(i.value for i in AssemblyItemType)

    _EXTENSIONS = {
        AssetType.VIDEO.value: ".mp4",
        AssetType.AUDIO.value: ".mp3",
    }

    def __init__(
        self,
        db: Session,
        storage: StorageBackend,
        command_runner: FFmpegCommandRunner | None = None,
        ffmpeg_binary: str = "ffmpeg",
        ffprobe_binary: str = "ffprobe",
    ) -> None:
        self._db = db
        self._storage = storage
        self._runner = command_runner or FFmpegCommandRunner(ffmpeg_binary)
        self._ffprobe = ffprobe_binary

    def render(
        self,
        series_id: str,
        assembly_id: str,
        output_path: str | Path | None = None,
    ) -> RenderResult:
        """Render the assembly and return a transient result."""
        assembly_service = VideoAssemblyService(self._db)
        try:
            assembly = assembly_service.get(series_id, assembly_id)
        except VideoAssemblyNotFoundError as exc:
            raise VideoRenderError(str(exc)) from exc

        if assembly.status == AssemblyStatus.RENDERING.value:
            raise AssemblyNotReadyError("Assembly is already rendering.")

        items = assembly_service.list_items(series_id, assembly_id)
        self._validate_assembly(assembly, items)

        caption_service = CaptionService(self._db)
        captions = caption_service.list_for_assembly(series_id, assembly_id)
        width, height = self._output_dimensions(assembly.output_config)

        try:
            assembly.status = AssemblyStatus.RENDERING.value
            self._db.flush()

            with tempfile.TemporaryDirectory(prefix="aivs_render_") as tmpdir_str:
                tmpdir = Path(tmpdir_str)
                materialized = self._materialize_assets(items, tmpdir)
                ass_path = self._build_ass_file(captions, tmpdir, width, height)
                output = Path(output_path) if output_path else tmpdir / "rendered.mp4"
                self._build_and_run(assembly, items, materialized, ass_path, output)
                result = self._validate_output(output, items)

            assembly.status = AssemblyStatus.READY.value
            self._db.flush()
            return result
        except Exception:
            assembly.status = AssemblyStatus.FAILED.value
            self._db.flush()
            raise

    def _validate_assembly(self, assembly: VideoAssembly, items: list[AssemblyItem]) -> None:
        if not items:
            raise InvalidTimelineError("Assembly has no timeline items to render.")

        total_video_end = 0.0
        prev_end = -1.0
        video_items = sorted(
            [i for i in items if i.item_type == AssemblyItemType.VIDEO.value],
            key=lambda x: x.start_time_seconds,
        )
        for item in items:
            asset = self._db.get(Asset, item.asset_id)
            if not asset or asset.series_id != assembly.series_id:
                raise MediaNotFoundError(
                    f"Asset for item {item.id} does not belong to this series."
                )
            if item.start_time_seconds < 0 or item.duration_seconds <= 0:
                raise InvalidTimelineError(
                    "Timeline items must have non-negative start and positive duration."
                )
            if item.item_type not in self.SUPPORTED_ITEM_TYPES:
                raise UnsupportedItemError(f"Unsupported assembly item type: {item.item_type}")

        for item in video_items:
            if item.start_time_seconds < prev_end:
                raise InvalidTimelineError("Overlapping video items are not supported.")
            end = item.start_time_seconds + item.duration_seconds
            prev_end = end
            if end > total_video_end:
                total_video_end = end

        total_audio_end = 0.0
        for item in items:
            end = item.start_time_seconds + item.duration_seconds
            if end > total_audio_end:
                total_audio_end = end

        total_duration = max(total_video_end, total_audio_end, assembly.duration_seconds or 0)
        if total_duration <= 0:
            raise InvalidTimelineError("Total assembly duration must be positive.")

    def _materialize_assets(
        self,
        items: list[AssemblyItem],
        tmpdir: Path,
    ) -> dict[str, Path]:
        """Copy referenced Assets to a temporary directory with safe names."""
        materialized: dict[str, Path] = {}
        asset_ids = {item.asset_id for item in items if item.asset_id}
        for asset_id in asset_ids:
            asset = self._db.get(Asset, asset_id)
            if not asset or not asset.storage_key:
                raise MediaNotFoundError(f"Asset {asset_id} is missing or has no storage key.")
            if not self._storage.exists(asset.storage_key):
                raise MediaNotFoundError(f"Asset {asset_id} not found in storage.")

            ext = self._EXTENSIONS.get(asset.asset_type, ".bin")
            path = tmpdir / f"asset_{asset_id}{ext}"
            stream = self._storage.get(asset.storage_key)
            try:
                path.write_bytes(_read_all(stream))
            finally:
                stream.close()
            materialized[asset_id] = path
        return materialized

    def _build_and_run(
        self,
        assembly: VideoAssembly,
        items: list[AssemblyItem],
        materialized: dict[str, Path],
        ass_path: Path | None,
        output: Path,
    ) -> None:
        width, height = self._output_dimensions(assembly.output_config)
        fps = _output_fps(assembly.output_config)

        video_items = sorted(
            [i for i in items if i.item_type == AssemblyItemType.VIDEO.value],
            key=lambda x: x.start_time_seconds,
        )
        audio_items = [i for i in items if i.item_type != AssemblyItemType.VIDEO.value]

        video_end = max([i.start_time_seconds + i.duration_seconds for i in video_items] or [0.0])
        audio_end = max([i.start_time_seconds + i.duration_seconds for i in audio_items] or [0.0])
        total_duration = max(video_end, audio_end, assembly.duration_seconds or 0)

        segments = self._build_video_segments(video_items, materialized, total_duration)

        inputs: list[tuple[str, str]] = []
        for segment in segments:
            if segment["is_black"]:
                inputs.append(
                    ("lavfi", f"color=c=black:s={width}x{height}:r={fps}:d={segment['duration']}")
                )
                inputs.append(
                    (
                        "lavfi",
                        f"anullsrc=channel_layout=stereo:sample_rate={self.SAMPLE_RATE}:d={segment['duration']}",
                    )
                )
            else:
                inputs.append(("file", str(segment["path"])))

        audio_inputs = []
        for item in audio_items:
            if not item.asset_id:
                raise MediaNotFoundError(f"Audio item {item.id} has no asset.")
            audio_inputs.append(("file", str(materialized[item.asset_id])))

        ffmpeg_args = ["-y"]
        for source, spec in inputs + audio_inputs:
            if source == "lavfi":
                ffmpeg_args.extend(["-f", "lavfi", "-i", spec])
            else:
                ffmpeg_args.extend(["-i", spec])

        filter_complex = self._build_filter_complex(
            segments,
            audio_items,
            width,
            height,
            total_duration,
            self.SAMPLE_RATE,
            ass_path,
        )
        ffmpeg_args.extend(["-filter_complex", filter_complex])
        ffmpeg_args.extend(
            [
                "-map",
                "[finalv]",
                "-map",
                "[finala]",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )

        returncode, stdout, stderr = self._runner.run(ffmpeg_args)
        if returncode != 0:
            raise FFmpegExecutionError(f"FFmpeg failed with code {returncode}: {stderr}")

    def _build_video_segments(
        self,
        video_items: list[AssemblyItem],
        materialized: dict[str, Path],
        total_duration: float,
    ) -> list[dict]:
        """Build contiguous video segments, inserting black fillers for gaps."""
        segments: list[dict] = []
        cursor = 0.0
        for item in video_items:
            if item.start_time_seconds > cursor:
                segments.append({"is_black": True, "duration": item.start_time_seconds - cursor})
                cursor = item.start_time_seconds
            segments.append(
                {
                    "is_black": False,
                    "path": materialized[item.asset_id],
                    "duration": item.duration_seconds,
                }
            )
            cursor += item.duration_seconds

        if cursor < total_duration:
            segments.append({"is_black": True, "duration": total_duration - cursor})

        if not segments:
            segments.append({"is_black": True, "duration": total_duration})

        return segments

    def _build_filter_complex(
        self,
        segments: list[dict],
        audio_items: list[AssemblyItem],
        width: int,
        height: int,
        total_duration: float,
        sample_rate: int,
        ass_path: Path | None,
    ) -> str:
        filters: list[str] = []
        segment_v_labels: list[str] = []
        segment_a_labels: list[str] = []

        input_idx = 0
        for seg_i, segment in enumerate(segments):
            v_in = f"[{input_idx}:v]"
            a_in = f"[{input_idx}:a]"
            input_idx += 1
            if segment["is_black"]:
                filters.append(
                    f"{v_in}trim=0:{segment['duration']},setpts=PTS-STARTPTS[vseg{seg_i}];"
                )
                filters.append(
                    f"{a_in}atrim=0:{segment['duration']},asetpts=PTS-STARTPTS,aresample={sample_rate},aformat=sample_fmts=fltp:sample_rates={sample_rate}:channel_layouts=stereo[aseg{seg_i}];"
                )
            else:
                filters.append(
                    f"{v_in}trim=0:{segment['duration']},setpts=PTS-STARTPTS,scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setdar=9/16[vseg{seg_i}];"
                )
                filters.append(
                    f"{a_in}atrim=0:{segment['duration']},asetpts=PTS-STARTPTS,aresample={sample_rate},aformat=sample_fmts=fltp:sample_rates={sample_rate}:channel_layouts=stereo[aseg{seg_i}];"
                )
            segment_v_labels.append(f"[vseg{seg_i}]")
            segment_a_labels.append(f"[aseg{seg_i}]")

        concat_inputs = "".join(segment_v_labels + segment_a_labels)
        num_segments = len(segments)
        filters.append(f"{concat_inputs}concat=n={num_segments}:v=1:a=1[vv][aa];")

        audio_labels = ["[aa]"]
        for idx, item in enumerate(audio_items):
            audio_in = f"[{input_idx}:a]"
            input_idx += 1
            duration = item.duration_seconds
            start = item.start_time_seconds
            delay_samples = int(start * sample_rate)

            loop_label = f"aloop{idx}"
            loop_filter = (
                f"{audio_in}aloop=loop=-1[{loop_label}];"
                if item.audio_cue and item.audio_cue.loop
                else ""
            )
            trim_input = f"[{loop_label}]" if item.audio_cue and item.audio_cue.loop else audio_in
            volume = (
                item.audio_cue.volume
                if item.audio_cue and item.audio_cue.volume is not None
                else 1.0
            )

            fade_part = ""
            fade_dur = min(0.5, duration / 2)
            if item.audio_cue:
                if item.audio_cue.fade_in:
                    fade_part += f",afade=t=in:ss=0:d={fade_dur}"
                if item.audio_cue.fade_out:
                    fade_part += f",afade=t=out:st={duration - fade_dur}:d={fade_dur}"

            filters.append(
                f"{loop_filter}{trim_input}atrim=0:{duration},asetpts=PTS-STARTPTS{fade_part},volume={volume},adelay=delays={delay_samples}|{delay_samples},aformat=sample_fmts=fltp:sample_rates={sample_rate}:channel_layouts=stereo[audio{idx}];"
            )
            audio_labels.append(f"[audio{idx}]")

        if len(audio_labels) == 1:
            filters.append(
                f"[aa]aformat=sample_fmts=fltp:sample_rates={sample_rate}:channel_layouts=stereo[finala];"
            )
        else:
            amix_inputs = "".join(audio_labels)
            num_audio = len(audio_labels)
            filters.append(
                f"{amix_inputs}amix=inputs={num_audio}:duration=first:normalize=0[finala];"
            )

        if ass_path is not None:
            filters.append(f"[vv]ass='{ass_path}'[vv_sub];[vv_sub]format=pix_fmts=yuv420p[finalv];")
        else:
            filters.append("[vv]format=pix_fmts=yuv420p[finalv];")

        return "".join(filters)

    def _build_ass_file(
        self,
        captions: list,
        tmpdir: Path,
        width: int,
        height: int,
    ) -> Path | None:
        """Generate an ASS subtitle file for caption burn-in, or None if no captions."""
        if not captions:
            return None

        service = CaptionService(self._db)
        ass_path = tmpdir / "captions.ass"

        lines = [
            "[Script Info]",
            "Title: AI Video Studio captions",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding",
        ]

        style = service.default_style()
        lines.append(
            f"Style: Default,{style.font_family},{style.font_size},"
            f"{style.primary_color},&H000000FF,{style.outline_color},&H80000000,"
            f"0,0,0,0,100,100,{style.line_spacing},0,1,{style.outline_width},"
            f"{style.shadow},{style.alignment},{style.margin_h},{style.margin_h},"
            f"{style.margin_v},1"
        )
        lines.append("")
        lines.append("[Events]")
        lines.append(
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        )

        for caption in captions:
            wrapped = service.wrap_text(caption.text, caption.style)
            start = self._ass_time(caption.start_time_seconds)
            end = self._ass_time(caption.end_time_seconds)
            safe_text = self._escape_ass_text(wrapped)
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{safe_text}")

        lines.append("")
        ass_path.write_text("\n".join(lines), encoding="utf-8")
        return ass_path

    @staticmethod
    def _ass_time(seconds: float) -> str:
        total = int(seconds)
        cs = int(round((seconds - total) * 100))
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    @staticmethod
    def _escape_ass_text(text: str) -> str:
        return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    def _validate_output(self, output: Path, items: list[AssemblyItem]) -> RenderResult:
        if not output.is_file():
            raise RenderOutputError("Rendered output file does not exist.")
        if output.stat().st_size == 0:
            raise RenderOutputError("Rendered output file is empty.")

        probe = self._ffprobe_output(output)
        video_stream = next(
            (s for s in probe.get("streams", []) if s.get("codec_type") == "video"),
            None,
        )
        audio_stream = next(
            (s for s in probe.get("streams", []) if s.get("codec_type") == "audio"),
            None,
        )

        if not video_stream:
            raise RenderOutputError("Rendered output has no video stream.")

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        if width == 0 or height == 0:
            raise RenderOutputError("Rendered output has invalid dimensions.")

        audio_items_present = any(i for i in items if i.item_type != AssemblyItemType.VIDEO.value)
        if audio_items_present and not audio_stream:
            raise RenderOutputError("Rendered output is missing an audio stream.")

        duration = float(probe.get("format", {}).get("duration", 0))
        size = output.stat().st_size
        container_format = probe.get("format", {}).get("format_name", "")

        if "mp4" not in container_format:
            raise RenderOutputError(f"Rendered output is not an MP4 container: {container_format}")

        return RenderResult(
            output_path=str(output),
            duration_seconds=duration,
            width=width,
            height=height,
            has_video_stream=True,
            has_audio_stream=audio_stream is not None,
            container_format=container_format,
            size_bytes=size,
            metadata={"ffprobe": probe},
        )

    def _ffprobe_output(self, output: Path) -> dict:
        if shutil.which(self._ffprobe) is None:
            raise RenderOutputError("ffprobe is not available for output validation.")

        cmd = [
            self._ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(output),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RenderOutputError(f"ffprobe failed: {proc.stderr}")
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RenderOutputError("ffprobe returned invalid JSON") from exc

    def _output_dimensions(self, output_config: dict | None) -> tuple[int, int]:
        if not output_config:
            return (self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        width = output_config.get("width", self.DEFAULT_WIDTH)
        height = output_config.get("height", self.DEFAULT_HEIGHT)
        return (int(width), int(height))


def _output_fps(output_config: dict | None) -> int:
    if not output_config:
        return FFmpegVideoRenderer.DEFAULT_FPS
    return int(output_config.get("frame_rate", FFmpegVideoRenderer.DEFAULT_FPS))


def _read_all(stream: BinaryIO) -> bytes:
    return stream.read()
