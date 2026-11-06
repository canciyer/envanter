"""CLI: offline scans for evaluation, or start Telegram polling."""
from __future__ import annotations

import argparse
import asyncio
import json
import os

from .service import analyze_video


def main() -> None:
    parser = argparse.ArgumentParser(description="PUBG Mobile inventory analyzer")
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="Analyze one locally stored video")
    scan.add_argument("video")
    commands.add_parser("bot", help="Run Telegram long-polling bot")
    for action in (scan, commands.choices["bot"]):
        action.add_argument(
            "--catalog",
            default=os.getenv("CATALOG_PATH", "data/catalog.json"),
        )
        action.add_argument(
            "--profile",
            default=os.getenv("PROFILE_PATH", "config/inventory_profile.json"),
        )
    args = parser.parse_args()
    if args.command == "bot":
        from .bot import run_bot

        asyncio.run(run_bot(catalog_path=args.catalog, profile_path=args.profile))
    else:
        report = analyze_video(
            args.video,
            catalog_path=args.catalog,
            profile_path=args.profile,
            max_video_mb=int(os.getenv("MAX_VIDEO_MB", "512")),
        )
        print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
