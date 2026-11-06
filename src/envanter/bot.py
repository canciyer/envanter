"""Aiogram transport. Analysis is deliberately fail-closed."""
from __future__ import annotations

import asyncio
from html import escape
import logging
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from .models import ScanReport
from .service import analyze_video
from .video import InvalidVideo

log = logging.getLogger(__name__)
EMOJI_ID = re.compile(r"^[0-9]{5,25}$")
MAX_TELEGRAM_DOWNLOAD_BYTES = 20 * 1024 * 1024


def render_report(report: ScanReport, *, custom_emoji: bool = False) -> str:
    lines = [
        "<b>🎮 PUBG Mobile — inventar analizi</b>",
        f"📹 Yoxlanan kadrlar: {report.frames_examined}",
        ("⚠️ Mythic sayı: qiymətləndirilməyib (etalon kataloqu boşdur)"
         if report.catalog_size == 0 else
         f"✅ Kataloq üzrə təsdiqlənmiş Mythic: <b>{report.confirmed_mythics}</b>"),
        "",
    ]
    if report.confirmed:
        lines.append("<b>Təsdiqlənmiş əşyalar:</b>")
        for item in report.confirmed:
            prefix = "🔹"
            if custom_emoji and item.emoji_id and EMOJI_ID.fullmatch(item.emoji_id):
                prefix = f'<tg-emoji emoji-id="{item.emoji_id}">🔹</tg-emoji>'
            lines.append(
                f"{prefix} {escape(item.name)} "
                f"({escape(item.kind)}, {escape(item.rarity)})"
            )
    else:
        lines.append("⚠️ Etalon bazası üzrə heç bir əşya təsdiqlənmədi.")
    lines.extend(
        [
            "",
            "ℹ️ Bu nəticə yalnız təsdiqlənmiş kataloq əşyalarını əhatə edir.",
            "Bu, hesabdakı bütün Mythic əşyaların dəqiq ümumi sayı deyil.",
        ]
    )
    if report.catalog_size == 0:
        lines.append(
            "⚠️ Etalon kataloqu boşdur; real inventar tanınması üçün "
            "təsdiqlənmiş şəkillər əlavə edilməlidir."
        )
    return "\n".join(lines)


def build_dispatcher(
    *,
    catalog_path: str,
    profile_path: str,
    max_mb: int,
    custom_emoji: bool,
    local_api: bool,
    concurrency: int = 2,
) -> Dispatcher:
    if not 1 <= concurrency <= 8:
        raise ValueError("Analysis concurrency must be 1–8")
    dp = Dispatcher()
    semaphore = asyncio.Semaphore(concurrency)

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(
            "🎮 PUBG Mobile inventar videosunu göndər (1–5 dəqiqə).\n"
            "Bot yalnız vizual olaraq təsdiqlənən kataloq əşyalarını sadalayır.\n"
            "Video kimi göndərmək tövsiyə olunur; video sənədi də qəbul edilir."
        )

    @dp.message(F.video | F.document)
    async def incoming_video(message: Message) -> None:
        media = message.video or message.document
        if media is None:
            return
        if message.document and not (
            (message.document.mime_type or "").lower().startswith("video/")
        ):
            await message.answer("❌ Zəhmət olmasa video faylı göndər.")
            return
        if message.video and media.duration is not None and not 60 <= media.duration <= 300:
            await message.answer("❌ Video 60–300 saniyə uzunluğunda olmalıdır.")
            return
        size = media.file_size
        if size is not None and size > max_mb * 1024 * 1024:
            await message.answer("❌ Video serverin ölçü limitini keçir.")
            return
        if not local_api and size is not None and size > MAX_TELEGRAM_DOWNLOAD_BYTES:
            await message.answer(
                "❌ Standart Telegram Bot API 20 MB-dan böyük faylları "
                "endirə bilmir. Kiçik video göndər və ya botu lokal API ilə işlət."
            )
            return
        status = await message.answer("⏳ Video yoxlanılır və analiz olunur...")
        async with semaphore:
            with TemporaryDirectory(prefix="envanter-upload-") as tmp:
                target = Path(tmp) / "inventory_video"
                try:
                    await message.bot.download(media, destination=target, timeout=120)
                    # Trust actual bytes and ffprobe, not user-provided metadata alone.
                    if target.stat().st_size > max_mb * 1024 * 1024:
                        raise InvalidVideo("Video exceeds configured size limit")
                    report = await asyncio.to_thread(
                        analyze_video, target, catalog_path, profile_path, max_mb
                    )
                    await status.edit_text(
                        render_report(report, custom_emoji=custom_emoji),
                        parse_mode=ParseMode.HTML,
                    )
                except InvalidVideo as exc:
                    await status.edit_text("❌ " + escape(str(exc)))
                except Exception:
                    log.exception("Video analysis failed")
                    await status.edit_text(
                        "❌ Analiz baş tutmadı. Video formatını və "
                        "server konfiqurasiyasını yoxlayın."
                    )

    return dp


async def run_bot(
    *,
    catalog_path: str = "data/catalog.json",
    profile_path: str = "config/inventory_profile.json",
) -> None:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is missing; set it in the environment")
    local_base = os.getenv("BOT_API_BASE", "").strip()
    max_mb = int(os.getenv("MAX_VIDEO_MB", "512"))
    custom_emoji = os.getenv("ENABLE_CUSTOM_EMOJI", "false").lower() == "true"
    concurrency = int(os.getenv("ANALYSIS_CONCURRENCY", "2"))
    session = (
        AiohttpSession(api=TelegramAPIServer.from_base(local_base, is_local=True))
        if local_base
        else AiohttpSession()
    )
    bot = Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = build_dispatcher(
        catalog_path=catalog_path,
        profile_path=profile_path,
        max_mb=max_mb,
        custom_emoji=custom_emoji,
        local_api=bool(local_base),
        concurrency=concurrency,
    )
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
