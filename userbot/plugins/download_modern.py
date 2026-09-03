import asyncio
import glob
import io
import os
import shutil
from pathlib import Path
from yt_dlp import YoutubeDL
from userbot import catub
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "media"


@catub.cat_cmd(
    pattern="(dl|download|media)(?:\\s|$)([\\s\\S]*)",
    command=("dl", plugin_category),
    info={
        "header": "Universal high-speed video/media downloader (YouTube, Insta, TikTok, Twitter, Reddit).",
        "usage": "{tr}dl <media link>",
    },
)
async def universal_downloader(event):
    "Universal Video Downloader"
    link = event.pattern_match.group(2).strip()
    reply = await event.get_reply_message()
    if not link and reply and reply.text:
        link = reply.text.strip()
    if not link:
        return await edit_delete(event, "`Please provide a media URL (YouTube, Instagram, TikTok, Twitter, Reddit)!`", 5)

    catevent = await edit_or_reply(event, "`⏳ Downloading media with modern engine...`")
    download_dir = Path("temp_downloads")
    download_dir.mkdir(exist_ok=True)
    out_tmpl = str(download_dir / "%(title).50s.%(ext)s")

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": out_tmpl,
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "max_filesize": 50 * 1024 * 1024,  # 50MB max for fast TG uploads
    }

    loop = asyncio.get_event_loop()

    def run_yt_dl():
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            return info

    try:
        info_dict = await loop.run_in_executor(None, run_yt_dl)
        downloaded_files = list(download_dir.glob("*"))
        if not downloaded_files:
            return await catevent.edit("`Could not find downloaded file!`")

        target_file = downloaded_files[0]
        title = info_dict.get("title", "Downloaded Video") if info_dict else "Media"
        duration = int(info_dict.get("duration", 0)) if info_dict else 0

        await catevent.edit("`📤 Uploading media to Telegram...`")
        await event.client.send_file(
            event.chat_id,
            target_file,
            caption=f"🎬 **{title}**",
            reply_to=reply.id if reply else None,
            attributes=[],
            supports_streaming=True,
        )
        await catevent.delete()
    except Exception as e:
        await catevent.edit(f"**Download failed:** `{e}`")
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)


@catub.cat_cmd(
    pattern="(music|song)(?:\\s|$)([\\s\\S]*)",
    command=("song", plugin_category),
    info={
        "header": "Search and download crystal-clear MP3 music with cover art.",
        "usage": "{tr}song <song title or artist>",
    },
)
async def modern_song_dl(event):
    "Fast MP3 Music Downloader"
    query = event.pattern_match.group(2).strip()
    reply = await event.get_reply_message()
    if not query and reply and reply.text:
        query = reply.text.strip()
    if not query:
        return await edit_delete(event, "`Please provide a song name or artist!`", 5)

    catevent = await edit_or_reply(event, f"`🎵 Searching and downloading '{query}'...`")
    download_dir = Path("temp_music")
    download_dir.mkdir(exist_ok=True)
    out_tmpl = str(download_dir / "%(title).50s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_tmpl,
        "default_search": "ytsearch1:",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
    }

    loop = asyncio.get_event_loop()

    def run_audio_dl():
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            return info

    try:
        info = await loop.run_in_executor(None, run_audio_dl)
        downloaded = list(download_dir.glob("*.mp3")) or list(download_dir.glob("*"))
        if not downloaded:
            return await catevent.edit(f"`No music found for: '{query}'`")

        target_file = downloaded[0]
        title = info.get("title", query) if info else query
        uploader = info.get("uploader", "Unknown Artist") if info else "Unknown"

        await catevent.edit("`📤 Uploading audio track...`")
        await event.client.send_file(
            event.chat_id,
            target_file,
            caption=f"🎧 **{title}**\n👤 **Artist:** `{uploader}`",
            reply_to=reply.id if reply else None,
        )
        await catevent.delete()
    except Exception as e:
        await catevent.edit(f"**Song download error:** `{e}`")
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)
