"""Synthetic regression tests; real PUBG clips are still required before production."""
from __future__ import annotations

import json

import cv2
import numpy as np
import pytest

from envanter.catalog import load_catalog
from envanter.models import InventoryProfile
from envanter.vision import scan_frames


def icon(color=(40, 180, 250), symbol="A") -> np.ndarray:
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    image[:] = (45, 55, 65)
    cv2.rectangle(image, (5, 6), (74, 74), color, -1)
    cv2.circle(image, (40, 42), 22, (20, 25, 110), -1)
    cv2.putText(image, symbol, (23, 53), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3)
    cv2.line(image, (0, 0), (79, 79), (70, 250, 20), 3)
    return image


def dataset(tmp_path, variants):
    entries = []
    for i, img in enumerate(variants):
        name = f"ref{i}.png"
        cv2.imwrite(str(tmp_path / name), img)
        entries.append({
            "id": f"item_{i}", "english_name": f"Known Item {i}",
            "kind": "set", "rarity": "mythic" if i == 0 else "legendary",
            "emoji_id": None, "templates": [name],
        })
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version": 1, "items": entries}), encoding="utf-8")
    return load_catalog(path)


def frame_of(img):
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[10:90, 10:90] = img
    return frame


PROFILE = InventoryProfile(
    roi=(0, 0, 1, 1), rows=1, columns=1, inset=0.1,
    sample_every_seconds=1, confirmation_frames=2,
)


def test_two_distinct_frames_confirm_one_mythic(tmp_path):
    sample = icon()
    items = dataset(tmp_path, [sample])
    report = scan_frames([(0, frame_of(sample)), (1, frame_of(sample))], items, PROFILE, 60)
    assert report.confirmed_mythics == 1
    assert len(report.confirmed) == 1
    assert report.confirmed[0].observed_frames == 2
    assert report.as_dict()["total_inventory_mythics_known"] is False


def test_single_frame_does_not_confirm(tmp_path):
    sample = icon()
    items = dataset(tmp_path, [sample])
    report = scan_frames([(0, frame_of(sample))], items, PROFILE, 60)
    assert report.confirmed == ()
    assert report.confirmed_mythics == 0


def test_repeated_item_does_not_inflate_counts(tmp_path):
    sample = icon()
    items = dataset(tmp_path, [sample])
    frames = [(i, frame_of(sample)) for i in range(5)]
    report = scan_frames(frames, items, PROFILE, 60)
    assert report.confirmed_mythics == 1
    assert report.confirmed[0].observed_frames == 5


def test_unknown_visual_is_not_falsely_labeled(tmp_path):
    items = dataset(tmp_path, [icon()])
    unknown = icon((220, 80, 30), "Z")
    report = scan_frames(
        [(0, frame_of(unknown)), (1, frame_of(unknown))], items, PROFILE, 60
    )
    assert report.confirmed == ()


def test_identical_references_are_ambiguous(tmp_path):
    sample = icon()
    items = dataset(tmp_path, [sample, sample.copy()])
    report = scan_frames(
        [(0, frame_of(sample)), (1, frame_of(sample))], items, PROFILE, 60
    )
    assert report.confirmed == ()


def test_empty_catalog_never_fabricates_detection():
    report = scan_frames(
        [(0, frame_of(icon())), (1, frame_of(icon()))], [], PROFILE, 60
    )
    assert report.confirmed == ()
    assert report.catalog_size == 0


def test_rejects_path_traversal(tmp_path):
    outside = tmp_path.parent / "outside.png"
    cv2.imwrite(str(outside), icon())
    catalog_path = tmp_path / "bad.json"
    catalog_path.write_text(json.dumps({
        "schema_version": 1, "items": [{
            "id": "test", "english_name": "Test", "kind": "set",
            "rarity": "mythic", "templates": ["../outside.png"],
        }]
    }))
    with pytest.raises(ValueError, match="inside catalog"):
        load_catalog(catalog_path)


def test_profile_validation(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({
        "roi": [0.9, 0.1, 0.2, 0.9], "rows": 4, "columns": 5
    }))
    with pytest.raises(ValueError, match="positive"):
        InventoryProfile.load(path)
