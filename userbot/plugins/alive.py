# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris UserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import random
import re
import time
from datetime import datetime
from platform import python_version

import requests
from telethon import version
from telethon.errors.rpcerrorlist import (
    MediaEmptyError,
    WebpageCurlFailedError,
    WebpageMediaEmptyError,
)
from telethon.events import CallbackQuery

from userbot import StartTime, catub, catversion

from ..Config import Config
from ..core.managers import edit_or_reply
from ..helpers.functions import catalive, check_data_base_heal_th, get_readable_time
from ..helpers.utils import reply_id
from ..sql_helper.globals import gvarstatus
from . import mention

plugin_category = "utils"


@catub.cat_cmd(
    pattern="alive$",
    command=("alive", plugin_category),
    info={
        "header": "To check Aetheris bot's alive status",
        "options": "To show media in this cmd you need to set ALIVE_PIC with media link, get this by replying the media by .tgm",
        "usage": [
            "{tr}alive",
        ],
    },
)
async def amireallyalive(event):
    "Aetheris Core status display"
    reply_to_id = await reply_id(event)
    ANIME = None
    cat_caption = gvarstatus("ALIVE_TEMPLATE") or temp
    if "ANIME" in cat_caption:
        try:
            data = requests.get("https://animechan.vercel.app/api/random", timeout=3).json()
            ANIME = f"**“{data['quote']}” - {data['character']} ({data['anime']})**"
        except Exception:
            ANIME = "**“Power is not will, it is the phenomenon of physically making things happen.”**"
    uptime = await get_readable_time((time.time() - StartTime))
    start = datetime.now()
    catevent = await edit_or_reply(event, "◈ `Querying Aetheris Core Diagnostics...`")
    end = datetime.now()
    ms = (end - start).microseconds / 1000
    _, check_sgnirts = check_data_base_heal_th()
    EMOJI = gvarstatus("ALIVE_EMOJI") or "▸"
    ALIVE_TEXT = gvarstatus("ALIVE_TEXT") or "◈ ─── ❖ **[ A E T H E R I S  C O R E ]** ❖ ─── ◈"
    CAT_IMG = gvarstatus("ALIVE_PIC")
    caption = cat_caption.format(
        ALIVE_TEXT=ALIVE_TEXT,
        ANIME=ANIME,
        EMOJI=EMOJI,
        mention=mention,
        uptime=uptime,
        telever=version.__version__,
        catver=catversion,
        pyver=python_version(),
        dbhealth=check_sgnirts,
        ping=ms,
    )
    if CAT_IMG:
        CAT = list(CAT_IMG.split())
        PIC = random.choice(CAT)
        try:
            await event.client.send_file(
                event.chat_id, PIC, caption=caption, reply_to=reply_to_id
            )
            await catevent.delete()
        except (WebpageMediaEmptyError, MediaEmptyError, WebpageCurlFailedError):
            return await edit_or_reply(
                catevent,
                f"**Media Value Error!**\n__Change the link by __`.setdv`\n\n**__Can't get media from this link :-**__ `{PIC}`",
            )
    else:
        await edit_or_reply(
            catevent,
            caption,
        )


temp = """◈ ─── ❖ **[ A E T H E R I S  C O R E ]** ❖ ─── ◈
**{EMOJI} Status    :** `Operational (Nominal)`
**{EMOJI} Engine    :** `Aetheris v{catver}`
**{EMOJI} Telethon  :** `v{telever}`
**{EMOJI} Python    :** `v{pyver}`
**{EMOJI} Database  :** `{dbhealth}`
**{EMOJI} Latency   :** `{ping} ms`
**{EMOJI} Uptime    :** `{uptime}`
**{EMOJI} Master    :** {mention}
◈ ───────────────────────────────────── ◈"""


def catalive_text():
    EMOJI = gvarstatus("ALIVE_EMOJI") or "▸"
    cat_caption = "◈ ─── **A E T H E R I S  C O R E** ─── ◈\n"
    cat_caption += f"**{EMOJI} Status   :** `Operational`\n"
    cat_caption += f"**{EMOJI} Engine   :** `Aetheris v{catversion}`\n"
    cat_caption += f"**{EMOJI} Telethon :** `v{version.__version__}`\n"
    cat_caption += f"**{EMOJI} Python   :** `v{python_version()}`\n"
    cat_caption += f"**{EMOJI} Master   :** {mention}\n"
    return cat_caption


@catub.cat_cmd(
    pattern="ialive$",
    command=("ialive", plugin_category),
    info={
        "header": "To check bot's alive status via inline mode",
        "options": "To show media in this cmd you need to set ALIVE_PIC with media link, get this by replying the media by .tgm",
        "usage": [
            "{tr}ialive",
        ],
    },
)
async def amireallyalive_inline(event):
    "Aetheris inline details"
    reply_to_id = await reply_id(event)
    results = await event.client.inline_query(Config.TG_BOT_USERNAME, "ialive")
    await results[0].click(event.chat_id, reply_to=reply_to_id, hide_via=True)
    await event.delete()


@catub.tgbot.on(CallbackQuery(data=re.compile(b"stats")))
async def on_plug_in_callback_query_handler(event):
    statstext = await catalive(StartTime)
    await event.answer(statstext, cache_time=0, alert=True)
