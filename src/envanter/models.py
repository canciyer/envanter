"""Validated project configuration and public results."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
from typing import Any


KINDS = frozenset({"set", "vehicle", "item"})
RARITIES = frozenset({"mythic", "legendary", "epic", "rare", "other"})


@dataclass(frozen=True)
class InventoryProfile:
    roi: tuple[float, float, float, float]
    rows: int
    columns: int
    inset: float = 0.10
    sample_every_seconds: float = 1.0
    confirmation_frames: int = 2

    @classmethod
    def load(cls, path: str | Path) -> "InventoryProfile":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Inventory profile must be a JSON object")
        if not isinstance(raw.get("roi"), list) or len(raw["roi"]) != 4:
            raise ValueError("Profile roi must have four normalized coordinates")
        roi = tuple(float(x) for x in raw["roi"])
        if not all(math.isfinite(x) and 0 <= x <= 1 for x in roi):
            raise ValueError("ROI values must be finite numbers between 0 and 1")
        if not (roi[0] < roi[2] and roi[1] < roi[3]):
            raise ValueError("ROI width and height must be positive")
        rows = int(raw["rows"])
        cols = int(raw["columns"])
        inset = float(raw.get("inset", 0.10))
        sample = float(raw.get("sample_every_seconds", 1.0))
        confirmations = int(raw.get("confirmation_frames", 2))
        if not 1 <= rows <= 20 or not 1 <= cols <= 20:
            raise ValueError("Rows and columns must be between 1 and 20")
        if not 0 <= inset < 0.40:
            raise ValueError("Inset must be between 0 and 0.40")
        if not math.isfinite(sample) or not 0.25 <= sample <= 10:
            raise ValueError("Sampling interval must be 0.25–10 seconds")
        if not 2 <= confirmations <= 10:
            raise ValueError("At least two independent confirmation frames required")
        return cls(roi, rows, cols, inset, sample, confirmations)


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    kind: str
    rarity: str
    emoji_id: str | None
    templates: tuple[Path, ...]


@dataclass(frozen=True)
class Recognition:
    item_id: str
    name: str
    kind: str
    rarity: str
    emoji_id: str | None
    score: float
    observed_frames: int


@dataclass(frozen=True)
class ScanReport:
    duration_seconds: float
    frames_examined: int
    confirmed: tuple[Recognition, ...]
    catalog_size: int

    @property
    def confirmed_mythics(self) -> int:
        return sum(item.rarity == "mythic" for item in self.confirmed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "duration_seconds": self.duration_seconds,
            "frames_examined": self.frames_examined,
            "confirmed_mythics": self.confirmed_mythics,
            "catalog_size": self.catalog_size,
            "confirmed": [
                {
                    "id": x.item_id,
                    "english_name": x.name,
                    "kind": x.kind,
                    "rarity": x.rarity,
                    "emoji_id": x.emoji_id,
                    "confidence_score": round(x.score, 4),
                    "observed_frames": x.observed_frames,
                }
                for x in self.confirmed
            ],
            "scope": "confirmed_catalog_items_only",
            "total_inventory_mythics_known": False,
        }
