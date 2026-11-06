from __future__ import annotations

import json
from subprocess import CompletedProcess

import pytest

from envanter.video import InvalidVideo, probe_video


def test_rejects_empty_video(tmp_path):
    path = tmp_path / "empty.mp4"
    path.write_bytes(b"")
    with pytest.raises(InvalidVideo, match="missing or empty"):
        probe_video(path)


def test_rejects_oversized_video_before_ffprobe(tmp_path):
    path = tmp_path / "large.mp4"
    path.write_bytes(b"abc")
    with pytest.raises(InvalidVideo, match="size limit"):
        probe_video(path, max_bytes=2)


@pytest.mark.parametrize("seconds", [0, 59.9, 300.1, 9999])
def test_duration_bounds(tmp_path, monkeypatch, seconds):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"not a video")
    def fake_run(*args, **kwargs):
        return CompletedProcess([], 0, stdout=json.dumps({
            "format": {"duration": seconds},
            "streams": [{"codec_type": "video", "width": 1280, "height": 720}]
        }))
    monkeypatch.setattr("envanter.video._run", fake_run)
    with pytest.raises(InvalidVideo, match="60 and 300"):
        probe_video(path)


def test_no_video_stream_rejected(tmp_path, monkeypatch):
    path = tmp_path / "audio.mp4"
    path.write_bytes(b"abc")
    monkeypatch.setattr("envanter.video._run", lambda *a, **k: CompletedProcess(
        [], 0, stdout=json.dumps({
            "format": {"duration": 120}, "streams": [{"codec_type": "audio"}]
        })
    ))
    with pytest.raises(InvalidVideo, match="metadata"):
        probe_video(path)
