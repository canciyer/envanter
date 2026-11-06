"""Curated item metadata and validated reference images."""
from __future__ import annotations

import json
from pathlib import Path
import re

import cv2
import numpy as np

from .models import Item, KINDS, RARITIES

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,79}$")
EMOJI_RE = re.compile(r"^[0-9]{5,25}$")


def load_catalog(path: str | Path) -> list[Item]:
    path = Path(path).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Unsupported catalog schema")
    entries = payload.get("items")
    if not isinstance(entries, list):
        raise ValueError("Catalog items must be an array")
    catalog: list[Item] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Catalog entry must be a JSON object")
        item_id = entry.get("id")
        name = entry.get("english_name")
        kind = entry.get("kind")
        rarity = entry.get("rarity")
        emoji_id = entry.get("emoji_id")
        templates = entry.get("templates")
        if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id):
            raise ValueError("Invalid catalog item id")
        if item_id in seen:
            raise ValueError("Duplicate catalog item id: " + item_id)
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError("Invalid English item name")
        if kind not in KINDS or rarity not in RARITIES:
            raise ValueError("Invalid item kind or rarity")
        if emoji_id is not None and (
            not isinstance(emoji_id, str) or not EMOJI_RE.fullmatch(emoji_id)
        ):
            raise ValueError("Invalid Telegram custom emoji ID")
        if not isinstance(templates, list) or not templates or len(templates) > 20:
            raise ValueError("Each item requires 1–20 reference images")
        paths: list[Path] = []
        for template in templates:
            if not isinstance(template, str) or not template.lower().endswith(
                (".png", ".jpg", ".jpeg", ".webp")
            ):
                raise ValueError("Reference must be an image path")
            absolute = (path.parent / template).resolve()
            if not absolute.is_relative_to(path.parent):
                raise ValueError("Reference path must stay inside catalog directory")
            if not absolute.is_file():
                raise ValueError("Reference image not found: " + str(absolute))
            image = cv2.imread(str(absolute), cv2.IMREAD_COLOR)
            if image is None or min(image.shape[:2]) < 24:
                raise ValueError("Invalid or tiny reference image: " + str(absolute))
            if float(np.std(image)) < 15:
                raise ValueError("Reference image lacks visual information")
            paths.append(absolute)
        seen.add(item_id)
        catalog.append(Item(item_id, name.strip(), kind, rarity, emoji_id, tuple(paths)))
    return catalog
