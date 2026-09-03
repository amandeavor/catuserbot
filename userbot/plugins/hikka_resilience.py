import asyncio
import json
import math
import urllib.parse
import aiohttp
from telethon.tl.functions.messages import ReadMentionsRequest
from userbot import catub
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "resilience"


@catub.cat_cmd(
    pattern="(markread|readall)$",
    command=("markread", plugin_category),
    info={
        "header": "Mark all chats and unread messages as read across your account.",
        "usage": "{tr}markread",
    },
)
async def mark_all_read(event):
    "Mark All Messages As Read"
    catevent = await edit_or_reply(event, "`📖 Marking all unread chats as read...`")
    read_count = 0
    try:
        async for dialog in event.client.iter_dialogs():
            if dialog.unread_count > 0:
                await event.client.send_read_acknowledge(dialog.entity)
                read_count += 1
                await asyncio.sleep(0.1)
        await catevent.edit(f"✅ **Successfully marked {read_count} unread chat(s) as read!**")
    except Exception as e:
        await catevent.edit(f"`Error marking chats as read: {e}`")


@catub.cat_cmd(
    pattern="(leave|kickme)$",
    command=("leave", plugin_category),
    info={
        "header": "Leave the current group or channel cleanly.",
        "usage": "{tr}leave",
    },
)
async def leave_chat(event):
    "Leave Current Chat"
    if event.is_private:
        return await edit_delete(event, "`You cannot leave a private DM!`", 5)

    await event.edit("👋 **Goodbye everyone! Leaving this group...**")
    await asyncio.sleep(1.5)
    try:
        await event.client.delete_dialog(event.chat_id)
    except Exception as e:
        await event.edit(f"`Failed to leave chat: {e}`")


@catub.cat_cmd(
    pattern="json$",
    command=("json", plugin_category),
    info={
        "header": "Dump the raw JSON metadata of the replied Telegram message.",
        "usage": "{tr}json (reply to message)",
    },
)
async def dump_json(event):
    "Dump Message JSON Metadata"
    reply = await event.get_reply_message()
    target = reply or event
    try:
        raw_dict = target.to_dict()
        # Convert non-serializable fields to strings
        json_str = json.dumps(raw_dict, indent=2, default=str)
        if len(json_str) > 4000:
            json_str = json_str[:3900] + "\n\n...(truncated)"
        await edit_or_reply(event, f"```json\n{json_str}\n```")
    except Exception as e:
        await edit_or_reply(event, f"`Failed to serialize JSON: {e}`")


@catub.cat_cmd(
    pattern="math(?:\\s|$)([\\s\\S]*)",
    command=("math", plugin_category),
    info={
        "header": "Safe scientific math calculator (supports sqrt, sin, cos, tan, log, pow, pi).",
        "usage": "{tr}math <expression> (e.g. {tr}math sqrt(144) * pi)",
    },
)
async def calculate_math(event):
    "Scientific Math Calculator"
    expr = event.pattern_match.group(1).strip()
    if not expr:
        return await edit_delete(event, "`Provide a math expression! (e.g. .math 2**8 + sqrt(100))`", 5)

    safe_dict = {
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
        "abs": abs,
        "round": round,
        "pow": pow,
    }

    try:
        # Evaluate safely without builtins
        result = eval(expr, {"__builtins__": None}, safe_dict)
        msg = f"🧮 **Math Evaluation:**\n\n📝 **Input:** `{expr}`\n💡 **Result:** `{result}`"
        await edit_or_reply(event, msg)
    except Exception as e:
        await edit_or_reply(event, f"❌ **Math Error:** `{e}`")


@catub.cat_cmd(
    pattern="figlet(?:\\s|$)([\\s\\S]*)",
    command=("figlet", plugin_category),
    info={
        "header": "Convert text into an ASCII art banner.",
        "usage": "{tr}figlet <text>",
    },
)
async def figlet_banner(event):
    "ASCII Banner Art"
    text = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not text and reply and reply.text:
        text = reply.text.strip()
    if not text:
        return await edit_delete(event, "`Provide text to convert into ASCII art!`", 5)

    catevent = await edit_or_reply(event, "`🎨 Generating ASCII art...`")
    encoded = urllib.parse.quote(text[:20])
    url = f"https://artii.herokuapp.com/make?text={encoded}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    banner = await resp.text()
                    await catevent.edit(f"```\n{banner}\n```")
                else:
                    await catevent.edit("`Could not generate banner!`")
    except Exception as e:
        await catevent.edit(f"`Figlet Error: {e}`")
