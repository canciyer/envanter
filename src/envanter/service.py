"""One synchronous analysis entry point shared by CLI and Telegram."""
from __future__ import annotations

from pathlib import Path

from .catalog import load_catalog
from .models import InventoryProfile, ScanReport
from .video import probe_video, sampled_frames
from .vision import scan_frames


def analyze_video(
    video_path: str | Path,
    catalog_path: str | Path = "data/catalog.json",
    profile_path: str | Path = "config/inventory_profile.json",
    max_video_mb: int = 512,
) -> ScanReport:
    if not 1 <= max_video_mb <= 2048:
        raise ValueError("max_video_mb must be between 1 and 2048")
    profile = InventoryProfile.load(profile_path)
    items = load_catalog(catalog_path)
    info = probe_video(video_path, max_bytes=max_video_mb * 1024 * 1024)
    return scan_frames(
        sampled_frames(video_path, profile),
        items,
        profile,
        duration_seconds=info.duration_seconds,
    )
