"""Strict multi-signal visual matching. No AI guesses or unverified detections."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import Iterable, Iterator

import cv2
import numpy as np

from .models import InventoryProfile, Item, Recognition, ScanReport


@dataclass(frozen=True)
class Signature:
    pixels: np.ndarray
    gray: np.ndarray
    phash: np.ndarray
    hist: np.ndarray
    texture: float


def signature(image: np.ndarray) -> Signature:
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected a BGR color image")
    pixels = cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(small))[:8, :8]
    values = dct.flatten()[1:]
    bits = values > np.median(values)
    hsv = cv2.cvtColor(pixels, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [24, 8], [0, 180, 0, 256])
    cv2.normalize(hist, hist, alpha=1.0, norm_type=cv2.NORM_L1)
    return Signature(pixels, gray, bits, hist, float(np.std(gray)))


@dataclass(frozen=True)
class _Template:
    item: Item
    signature: Signature


@dataclass(frozen=True)
class _Candidate:
    item: Item
    score: float


def extract_tiles(frame: np.ndarray, profile: InventoryProfile) -> Iterator[np.ndarray]:
    if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("Expected a video frame in BGR format")
    height, width = frame.shape[:2]
    left, top, right, bottom = profile.roi
    x0, y0 = round(left * width), round(top * height)
    x1, y1 = round(right * width), round(bottom * height)
    w, h = x1 - x0, y1 - y0
    if w < profile.columns * 28 or h < profile.rows * 28:
        raise ValueError("Inventory grid too small for reliable analysis")
    for row in range(profile.rows):
        for col in range(profile.columns):
            a = x0 + round(col * w / profile.columns)
            b = x0 + round((col + 1) * w / profile.columns)
            c = y0 + round(row * h / profile.rows)
            d = y0 + round((row + 1) * h / profile.rows)
            inset_x = round((b - a) * profile.inset)
            inset_y = round((d - c) * profile.inset)
            tile = frame[c + inset_y : d - inset_y, a + inset_x : b - inset_x]
            if tile.size:
                yield tile


def _compare(x: Signature, y: Signature) -> tuple[float, bool]:
    if x.texture < 18 or y.texture < 18:
        return 0.0, False
    corr = float(cv2.matchTemplate(x.gray, y.gray, cv2.TM_CCOEFF_NORMED)[0, 0])
    if not math.isfinite(corr):
        return 0.0, False
    phash_distance = int(np.count_nonzero(x.phash != y.phash))
    hist_distance = float(cv2.compareHist(x.hist, y.hist, cv2.HISTCMP_BHATTACHARYYA))
    pixel_difference = float(np.mean(cv2.absdiff(x.pixels, y.pixels))) / 255.0
    score = (
        0.45 * max(0.0, corr)
        + 0.25 * max(0.0, 1.0 - phash_distance / 63.0)
        + 0.20 * max(0.0, 1.0 - hist_distance)
        + 0.10 * max(0.0, 1.0 - pixel_difference)
    )
    # All checks must pass independently; a single very high score cannot hide a mismatch.
    admissible = (
        corr >= 0.96
        and phash_distance <= 6
        and hist_distance <= 0.22
        and pixel_difference <= 0.11
    )
    return score, admissible


class ConservativeMatcher:
    def __init__(self, items: list[Item], profile: InventoryProfile) -> None:
        self.items = items
        self.profile = profile
        self.templates: list[_Template] = []
        for item in items:
            for path in item.templates:
                image = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if image is None:
                    raise ValueError("Cannot read template: " + str(path))
                s = signature(image)
                if s.texture < 18:
                    raise ValueError("Reference is not distinctive enough: " + str(path))
                self.templates.append(_Template(item, s))

    def match(self, tile: np.ndarray) -> _Candidate | None:
        if not self.templates:
            return None
        try:
            seen = signature(tile)
        except (cv2.error, ValueError):
            return None
        if seen.texture < 18:
            return None
        per_item: dict[str, tuple[float, bool, Item]] = {}
        for reference in self.templates:
            score, allowed = _compare(seen, reference.signature)
            previous = per_item.get(reference.item.id)
            if previous is None or score > previous[0]:
                per_item[reference.item.id] = (score, allowed, reference.item)
        ordered = sorted(per_item.values(), key=lambda x: x[0], reverse=True)
        if not ordered or not ordered[0][1]:
            return None
        # Reject another catalog item whose appearance is too similar.
        if len(ordered) > 1 and ordered[0][0] - ordered[1][0] < 0.045:
            return None
        best = ordered[0]
        return _Candidate(best[2], best[0])


def scan_frames(
    frames: Iterable[tuple[float, np.ndarray]],
    items: list[Item],
    profile: InventoryProfile,
    duration_seconds: float = 0,
) -> ScanReport:
    matcher = ConservativeMatcher(items, profile)
    sightings: dict[str, set[int]] = defaultdict(set)
    scores: dict[str, float] = {}
    count = 0
    for frame_number, (_, frame) in enumerate(frames):
        count += 1
        # Same item seen in 20 cells of one frame still supplies only one observation.
        per_frame: dict[str, float] = {}
        for tile in extract_tiles(frame, profile):
            match = matcher.match(tile)
            if match:
                per_frame[match.item.id] = max(
                    per_frame.get(match.item.id, 0.0), match.score
                )
        for item_id, score in per_frame.items():
            sightings[item_id].add(frame_number)
            scores[item_id] = max(scores.get(item_id, 0.0), score)
    verified = [
        Recognition(
            item_id=item.id,
            name=item.name,
            kind=item.kind,
            rarity=item.rarity,
            emoji_id=item.emoji_id,
            score=scores[item.id],
            observed_frames=len(sightings[item.id]),
        )
        for item in items
        if len(sightings[item.id]) >= profile.confirmation_frames
    ]
    verified.sort(key=lambda x: (x.kind, x.name))
    return ScanReport(duration_seconds, count, tuple(verified), len(items))
