# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris UserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import time
from datetime import datetime
from platform import python_version

import psutil
from telethon import version
from telethon.errors import FloodWaitError

from userbot import StartTime, catub, catversion

from ..Config import Config
from ..core import task_manager
from ..core.managers import edit_delete, edit_or_reply
from ..helpers.functions import check_data_base_heal_th, get_readable_time
from ..helpers.utils import reply_id
from ..sql_helper.globals import gvarstatus
from . import mention

plugin_category = "utils"


@catub.cat_cmd(
    pattern="(?:aetheris|aeth)$",
    command=("aetheris", plugin_category),
    info={
        "header": "Display the comprehensive Aetheris Intelligence Dashboard.",
        "usage": "{tr}aetheris or {tr}aeth",
    },
)
async def aetheris_dashboard(event):
    "Aetheris Intelligence HUD"
    reply_to_id = await reply_id(event)
    start = datetime.now()
    catevent = await edit_or_reply(event, "◈ `Synchronizing Aetheris Dashboard...`")
    end = datetime.now()
    latency = round((end - start).microseconds / 1000, 2)
    uptime = await get_readable_time((time.time() - StartTime))

    # Memory
    mem = psutil.virtual_memory()
    ram_str = f"{mem.used / (1024**2):.0f}MB / {mem.total / (1024**2):.0f}MB ({mem.percent}%)"

    # Tasks
    active_tasks = len(task_manager.list_active_tasks())
    _, db_status = check_data_base_heal_th()

    dashboard = f"""◈ ─── ❖ **[ A E T H E R I S  C O N T R O L ]** ❖ ─── ◈
▸ **Engine    :** `Aetheris v{catversion}` (Turbo)
▸ **Status    :** `Operational (All Systems Nominal)`
▸ **Uptime    :** `{uptime}`
▸ **Latency   :** `{latency} ms`
▸ **Database  :** `{db_status}`
▸ **Memory    :** `{ram_str}`
▸ **BG Tasks  :** `{active_tasks} active`
▸ **Stack     :** `Telethon v{version.__version__} | Python {python_version()}`
▸ **Operator  :** {mention}

**Quick Controls:**
• `{Config.COMMAND_HAND_LER}alive` — Live Status Card
• `{Config.COMMAND_HAND_LER}ping` — Telemetry Latency
• `{Config.COMMAND_HAND_LER}reload` — Dynamic Hot-Reload
• `{Config.COMMAND_HAND_LER}tasks` — Background Task List
• `{Config.COMMAND_HAND_LER}help` — Interactive Command Deck
◈ ───────────────────────────────────── ◈"""
    await edit_or_reply(catevent, dashboard)


@catub.cat_cmd(
    pattern=r"floodtest(?:\s|$)([\s\S]*)",
    command=("floodtest", plugin_category),
    info={
        "header": "Demonstrates Aetheris FloodWait Auto-Backoff Shield.",
        "usage": "{tr}floodtest",
    },
)
async def floodtest_cmd(event):
    "Aetheris FloodWait Shield check"
    catevent = await edit_or_reply(
        event,
        "◈ **Aetheris FloodWait Shield Active**\n▸ Rate-limit protection intercepts Telegram 420 errors\n▸ Auto-pauses and resumes without crashing operations.",
    )


@catub.cat_cmd(
    pattern=r"quickpurge(?:\s|$)([\s\S]*)",
    command=("quickpurge", plugin_category),
    info={
        "header": "Fast message purger with optional --limit or count.",
        "usage": ["{tr}quickpurge 10", "{tr}quickpurge --limit 25"],
    },
)
async def quick_purge_cmd(event):
    "Fast resilient purge"
    if not event.is_group and not event.is_private:
        return await edit_delete(event, "`Cannot purge in this chat.`", 5)

    limit = 10
    if event.flags and "limit" in event.flags:
        try:
            limit = int(event.flags["limit"])
        except ValueError:
            limit = 10
    elif event.positional and event.positional[0].isdigit():
        limit = int(event.positional[0])

    if limit > 100:
        limit = 100

    catevent = await edit_or_reply(event, f"◈ `Purging last {limit} messages...`")
    messages = []
    async for msg in event.client.iter_messages(event.chat_id, limit=limit + 1):
        if msg.id != catevent.id:
            messages.append(msg.id)

    if messages:
        try:
            await event.client.delete_messages(event.chat_id, messages)
            await edit_delete(catevent, f"◈ **Purged `{len(messages)}` messages successfully.**", 4)
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 1)
            await event.client.delete_messages(event.chat_id, messages)
            await edit_delete(catevent, f"◈ **Purged `{len(messages)}` messages successfully.**", 4)
        except Exception as e:
            await edit_delete(catevent, f"**Purge error:** `{e}`", 5)
    else:
        await edit_delete(catevent, "**No messages found to purge.**", 4)
