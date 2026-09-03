import asyncio
from userbot import catub
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "stealth"


@catub.cat_cmd(
    pattern="(saved|grab|save)(?:\\s|$)([\\s\\S]*)",
    command=("saved", plugin_category),
    info={
        "header": "Bypass restricted / copy-protected channels and save media directly to your Saved Messages.",
        "usage": "{tr}saved (reply to media/message) or {tr}saved <count>",
    },
)
async def save_restricted_media(event):
    "Save Restricted Content to Saved Messages"
    reply = await event.get_reply_message()
    count_str = event.pattern_match.group(2).strip()

    catevent = await edit_or_reply(event, "`🔒 Grabbing restricted media...`")
    me = await event.client.get_me()

    if reply:
        try:
            if reply.media:
                downloaded = await reply.download_media()
                await event.client.send_file(
                    me.id,
                    downloaded,
                    caption=reply.text or "",
                )
            elif reply.text:
                await event.client.send_message(me.id, reply.text)
            await catevent.edit("✅ **Successfully saved to your Saved Messages!**")
        except Exception as e:
            await catevent.edit(f"`Failed to grab message: {e}`")
        return

    # If count is specified, grab last N messages from chat
    try:
        count = int(count_str) if count_str.isdigit() else 1
    except ValueError:
        count = 1

    count = min(count, 15)
    saved_total = 0
    async for msg in event.client.iter_messages(event.chat_id, limit=count):
        try:
            if msg.media:
                f = await msg.download_media()
                await event.client.send_file(me.id, f, caption=msg.text or "")
                saved_total += 1
            elif msg.text:
                await event.client.send_message(me.id, msg.text)
                saved_total += 1
            await asyncio.sleep(0.5)
        except Exception:
            pass

    await catevent.edit(f"✅ **Saved `{saved_total}` message(s) to Saved Messages!**")
