# Envanter — PUBG Mobile inventory video analyzer

Conservative Telegram bot and CLI for inspecting 1–5 minute PUBG Mobile inventory recordings. **This is an MVP, not a trained or production-validated recognition system.** The initial catalog is intentionally empty: no PUBG items can be recognized until real verified reference icons are added.

## What works

- aiogram bot receives videos and video documents; checks duration, dimensions and disk size using ffprobe.
- FFmpeg samples 1 frame per second at configurable resolution; OpenCV crops an inventory grid.
- Matches icons against a curated catalog using independent grayscale correlation, perceptual hash, color histogram and pixel-difference thresholds.
- Rejects ambiguous or low-quality matches. A candidate must appear in at least two distinct sampled frames.
- Deduplicates by catalog item ID, emits canonical English names and optional custom emoji IDs.
- CLI JSON output, unit tests, GitHub Actions CI configuration.

**The number reported is confirmed catalog-matched Mythic IDs, not the guaranteed total Mythic item count in a player's inventory.** Unknown items are rejected. Collection-level OCR and arbitrary scrolling-layout detection are not implemented yet. Zero false positives cannot be guaranteed without representative real-video evaluation.

## Setup

Requires Python 3.11+, FFmpeg and ffprobe:

```bash
sudo apt-get update && sudo apt-get install -y ffmpeg python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
pytest -q
```

To scan a local file:

```bash
python -m envanter scan /path/to/inventory.mp4
```

To run the Telegram bot, copy `.env.example` to `.env`, supply your private BotFather `BOT_TOKEN`, export the environment variables, then run:

```bash
set -a; source .env; set +a
python -m envanter bot
```

Never commit tokens or user videos. Files are temporary while a message is processed.

### Telegram download limits

The standard cloud Bot API's `getFile` download limit is 20 MB. Larger uploads require operating a **local Telegram Bot API server** and setting `BOT_API_BASE` appropriately; merely raising `MAX_VIDEO_MB` cannot bypass Telegram's cloud limit. A secure local Bot API deployment is a separate requirement, not bundled.

### Curated reference catalog

Add only manually verified, authorized reference image crops under `data/references/`; update `data/catalog.json` entries like:

```json
{
  "schema_version": 1,
  "items": [{
    "id": "verified_slug",
    "english_name": "Verified official English name",
    "kind": "set",
    "rarity": "mythic",
    "emoji_id": null,
    "templates": ["references/verified_slug/front.png"]
  }]
}
```

The path must be inside the catalog directory. The catalog ID and English name must be confirmed against trusted evidence. The match engine never invents item IDs.

### Calibrate grid geometry

The supplied `config/inventory_profile.json` is a **placeholder**, not an assertion about real PUBG Mobile inventory geometry. It defines normalized grid region `roi`, rows, columns, border inset, temporal sampling and required independent confirmation frames. Real video samples are required to determine correct geometry. Reference crops should resemble the cropped icon interior, not screenshots of the entire inventory.

## False-positive policy

A potential match is rejected unless all four similarity checks pass and the best match is sufficiently separated from alternative catalog entries. Multiple sightings of the same ID are counted once. These safeguards reduce false positives, but restrictive matching can also cause false negatives. Do not show a zero count as a claim that a real inventory contains no Mythics.

## Limitations and next milestones

1. Obtain permissioned PUBG Mobile video captures and labeled icon crops, with near-duplicate negatives.
2. Build multiple grid profiles or a learned UI detector for different screen layouts, scroll speeds and seasons.
3. Calibrate thresholds on training data; keep a disjoint holdout set for unbiased precision/recall evaluation.
4. Add OCR with cross-frame verification for the optional collection level.
5. Add job persistence, input quotas and upload protections for high-traffic production operation.
6. Test Telegram custom emoji eligibility and 100–200 MB uploads against a deployed local Bot API server.

See [dataset and evaluation plan](docs/DATASET.md) for proposed acceptance criteria.
