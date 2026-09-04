# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris UserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import random
import time
from datetime import datetime

import requests
from telethon.errors.rpcerrorlist import (
    MediaEmptyError,
    WebpageCurlFailedError,
    WebpageMediaEmptyError,
)

from ..Config import Config
from ..core.managers import edit_or_reply
from ..helpers.functions import get_readable_time
from ..sql_helper.globals import gvarstatus
from . import StartTime, catub, mention, reply_id

plugin_category = "tools"

temp_ = "◈ `Pinging Aetheris Network...`"
temp = """◈ ─── ❖ **[ A E T H E R I S ]** ❖ ─── ◈
⚡ **Latency :** `{ping} ms`
⏳ **Uptime  :** `{uptime}`
◈ ─────────────────────────── ◈"""

if Config.BADCAT:
    temp_ = "◈ `[Aetheris // Ping]`"
    temp = """◈ ─── **A E T H E R I S** ─── ◈
⚡ **Latency :** `{ping} ms`
⏳ **Uptime  :** `{uptime}`
👤 **Master  :** {mention}
◈ ─────────────────── ◈"""


@catub.cat_cmd(
    pattern="ping( -a|$)",
    command=("ping", plugin_category),
    info={
        "header": "Check roundtrip latency to Telegram servers",
        "flags": {"-a": "average ping over 3 samples"},
        "usage": ["{tr}ping", "{tr}ping -a"],
    },
)
async def ping_cmd(event):
    "To check ping and latency"
    flag = event.pattern_match.group(1)
    reply_to_id = await reply_id(event)
    uptime = await get_readable_time((time.time() - StartTime))
    start = datetime.now()
    if flag == " -a":
        catevent = await edit_or_reply(event, "◈ `[ ▰▱▱ ] Sampling latency...`")
        await asyncio.sleep(0.25)
        await edit_or_reply(catevent, "◈ `[ ▰▰▱ ] Measuring telemetry...`")
        await asyncio.sleep(0.25)
        await edit_or_reply(catevent, "◈ `[ ▰▰▰ ] Finalizing stats...`")
        end = datetime.now()
        tms = (end - start).microseconds / 1000
        ms = round((tms - 0.5) / 3, 3)
        await edit_or_reply(
            catevent,
            f"◈ ─── **A E T H E R I S  P I N G** ─── ◈\n⚡ **Avg Latency :** `{ms} ms`\n⏳ **Uptime      :** `{uptime}`\n◈ ──────────────────────────── ◈",
        )
    else:
        catevent = await edit_or_reply(event, temp_)
        end = datetime.now()
        ms = (end - start).microseconds / 1000
        ANIME = None
        ping_temp = gvarstatus("PING_TEMPLATE") or temp
        PING_PIC = gvarstatus("PING_PIC")
        if "ANIME" in ping_temp:
            try:
                data = requests.get("https://animechan.vercel.app/api/random", timeout=3).json()
                ANIME = f"**“{data['quote']}” - {data['character']} ({data['anime']})**"
            except Exception:
                ANIME = "**“Move fast and build clean systems.”**"
        caption = ping_temp.format(
            ANIME=ANIME,
            mention=mention,
            uptime=uptime,
            ping=ms,
        )
        if PING_PIC:
            CAT = list(PING_PIC.split())
            PIC = random.choice(CAT)
            try:
                await event.client.send_file(
                    event.chat_id, PIC, caption=caption, reply_to=reply_to_id
                )
                await catevent.delete()
            except (WebpageMediaEmptyError, MediaEmptyError, WebpageCurlFailedError):
                return await edit_or_reply(
                    catevent,
                    f"**Media Value Error!**\n__Change the link with __`.setdv`\n\n**__Can't get media from link:__** `{PIC}`",
                )
        else:
            await edit_or_reply(
                catevent,
                caption,
            )
