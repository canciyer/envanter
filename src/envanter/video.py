"""Bounded FFmpeg ingestion: never load an entire video into memory."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from typing import Iterator

import cv2

from .models import InventoryProfile


class InvalidVideo(ValueError):
    pass


@dataclass(frozen=True)
class VideoInfo:
    duration_seconds: float
    width: int
    height: int
    size_bytes: int


def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=True
        )
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg and ffprobe must be installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise InvalidVideo("Video decoding timed out") from exc
    except subprocess.CalledProcessError as exc:
        raise InvalidVideo("Video cannot be decoded safely") from exc


def probe_video(path: str | Path, max_bytes: int = 512 * 1024 * 1024) -> VideoInfo:
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise InvalidVideo("Video file is missing or empty")
    if path.stat().st_size > max_bytes:
        raise InvalidVideo("Video exceeds configured size limit")
    response = _run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of", "json", str(path),
        ],
        timeout=30,
    )
    try:
        data = json.loads(response.stdout)
        streams = [s for s in data["streams"] if s.get("codec_type") == "video"]
        if not streams:
            raise ValueError("No video stream")
        stream = streams[0]
        duration = float(data["format"]["duration"])
        width, height = int(stream["width"]), int(stream["height"])
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
        raise InvalidVideo("Missing or invalid video metadata") from exc
    if not 60 <= duration <= 300:
        raise InvalidVideo("Video duration must be between 60 and 300 seconds")
    if not 160 <= width <= 4096 or not 160 <= height <= 4096:
        raise InvalidVideo("Video dimensions are not supported")
    return VideoInfo(duration, width, height, path.stat().st_size)


def sampled_frames(
    path: str | Path, profile: InventoryProfile, *, timeout: int = 180
) -> Iterator[tuple[float, object]]:
    # Temp directory remains alive while caller consumes the iterator.
    with TemporaryDirectory(prefix="envanter-frames-") as temp:
        fps = 1.0 / profile.sample_every_seconds
        output = str(Path(temp) / "frame_%05d.jpg")
        _run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-i", str(path), "-an", "-sn", "-dn",
                "-vf", f"fps={fps:.8f},scale=1280:-2:flags=area",
                "-frames:v", str(min(1200, int(300 / profile.sample_every_seconds) + 2)),
                "-q:v", "2", output,
            ],
            timeout=timeout,
        )
        paths = sorted(Path(temp).glob("frame_*.jpg"))
        if not paths:
            raise InvalidVideo("No readable frames in video")
        for index, frame_path in enumerate(paths):
            image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
            if image is not None:
                yield index * profile.sample_every_seconds, image
