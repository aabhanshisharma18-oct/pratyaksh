"""Bounded FFmpeg video probing and timestamp-based frame extraction for D1."""
from __future__ import annotations

import io
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, UnidentifiedImageError


MAX_DURATION_SECONDS = 120.0
MAX_DECODED_PIXELS = 20_000_000
MAX_SAMPLES = 12
SAMPLE_INTERVAL_SECONDS = 2.0
PROBE_TIMEOUT_SECONDS = 20
FRAME_TIMEOUT_SECONDS = 15


class VideoProbeError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class VideoSampler:
    """Inspect one bounded video and decode frames at recorded presentation times."""

    @staticmethod
    def available() -> bool:
        return shutil.which("ffprobe") is not None and shutil.which("ffmpeg") is not None

    @staticmethod
    def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise VideoProbeError(422, "Video inspection exceeded the time limit") from exc
        except OSError as exc:
            raise VideoProbeError(503, "FFmpeg and FFprobe are required for video analysis") from exc

    @staticmethod
    def _json_output(process: subprocess.CompletedProcess[bytes], failure: str) -> dict:
        if process.returncode != 0:
            raise VideoProbeError(422, failure)
        try:
            return json.loads(process.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VideoProbeError(422, failure) from exc

    @staticmethod
    def _choose_timestamps(frame_times_ms: list[int], duration_ms: int, max_samples: int = MAX_SAMPLES) -> list[int]:
        if not frame_times_ms or duration_ms <= 0:
            raise VideoProbeError(422, "Video frame timestamps are unavailable")
        count = min(
            max_samples,
            max(1, math.ceil((duration_ms / 1000) / SAMPLE_INTERVAL_SECONDS)),
        )
        targets = [round((index + 0.5) * duration_ms / count) for index in range(count)]
        selected: list[int] = []
        for target in targets:
            closest = min(frame_times_ms, key=lambda value: abs(value - target))
            if closest not in selected:
                selected.append(closest)
        return selected

    def sample(self, raw: bytes, filename: str | None = None, *, max_samples: int = MAX_SAMPLES) -> dict:
        if not self.available():
            raise VideoProbeError(503, "FFmpeg and FFprobe are required for video analysis")

        suffix = Path(filename or "video.mp4").suffix.lower()
        if not suffix or len(suffix) > 10:
            suffix = ".video"

        with tempfile.TemporaryDirectory(prefix="pratyaksh-video-") as folder:
            source = Path(folder) / f"source{suffix}"
            source.write_bytes(raw)
            path = str(source)

            metadata_process = self._run(
                [
                    "ffprobe", "-v", "error", "-show_entries",
                    "format=duration,format_name:stream=index,codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,duration",
                    "-of", "json", path,
                ],
                PROBE_TIMEOUT_SECONDS,
            )
            metadata_payload = self._json_output(
                metadata_process, "Video container or streams could not be decoded"
            )
            video_streams = [
                stream for stream in metadata_payload.get("streams", [])
                if stream.get("codec_type") == "video"
            ]
            if not video_streams:
                raise VideoProbeError(415, "The file contains no decodable video stream")
            stream = video_streams[0]
            try:
                width = int(stream["width"])
                height = int(stream["height"])
                duration = float(
                    metadata_payload.get("format", {}).get("duration")
                    or stream.get("duration")
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise VideoProbeError(422, "Video dimensions or duration are unavailable") from exc
            if width < 32 or height < 32 or width * height > MAX_DECODED_PIXELS:
                raise VideoProbeError(422, "Video dimensions are outside the supported limits")
            if not math.isfinite(duration) or duration <= 0:
                raise VideoProbeError(422, "Video duration is invalid")
            if duration > MAX_DURATION_SECONDS:
                raise VideoProbeError(413, "Video exceeds the 120 second analysis limit")

            frames_process = self._run(
                [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_frames", "-show_entries", "frame=best_effort_timestamp_time",
                    "-of", "json", path,
                ],
                PROBE_TIMEOUT_SECONDS,
            )
            frames_payload = self._json_output(
                frames_process, "Video frame timestamps could not be read"
            )
            frame_times_ms: list[int] = []
            for frame in frames_payload.get("frames", []):
                try:
                    timestamp = float(frame["best_effort_timestamp_time"])
                except (KeyError, TypeError, ValueError):
                    continue
                if math.isfinite(timestamp) and timestamp >= 0:
                    frame_times_ms.append(round(timestamp * 1000))
            frame_times_ms = sorted(set(frame_times_ms))
            duration_ms = round(duration * 1000)
            selected = self._choose_timestamps(frame_times_ms, duration_ms, max_samples)

            decoded = []
            rejected = []
            for timestamp_ms in selected:
                frame_process = self._run(
                    [
                        "ffmpeg", "-v", "error", "-ss", f"{timestamp_ms / 1000:.6f}",
                        "-i", path, "-map", "0:v:0", "-frames:v", "1",
                        "-f", "image2pipe", "-vcodec", "png", "pipe:1",
                    ],
                    FRAME_TIMEOUT_SECONDS,
                )
                if frame_process.returncode != 0 or not frame_process.stdout:
                    rejected.append({"timestamp_ms": timestamp_ms, "reason": "frame_decode_failed"})
                    continue
                try:
                    with Image.open(io.BytesIO(frame_process.stdout)) as image:
                        image.load()
                        decoded.append({"timestamp_ms": timestamp_ms, "image": image.convert("RGB")})
                except (UnidentifiedImageError, OSError, ValueError):
                    rejected.append({"timestamp_ms": timestamp_ms, "reason": "frame_decode_failed"})

        if not decoded:
            raise VideoProbeError(422, "No sampled video frame could be decoded")
        return {
            "metadata": {
                "container": metadata_payload.get("format", {}).get("format_name", "unknown"),
                "codec": stream.get("codec_name", "unknown"),
                "width": width,
                "height": height,
                "duration_ms": duration_ms,
                "average_frame_rate": stream.get("avg_frame_rate", "unknown"),
                "nominal_frame_rate": stream.get("r_frame_rate", "unknown"),
                "source_frame_timestamps": len(frame_times_ms),
            },
            "requested_count": len(selected),
            "frames": decoded,
            "rejected": rejected,
        }
