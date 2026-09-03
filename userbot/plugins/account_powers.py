import asyncio
import time
from userbot import catub
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "account"


@catub.cat_cmd(
    pattern="purgeme(?:\\s|$)([\\s\\S]*)",
    command=("purgeme", plugin_category),
    info={
        "header": "Purge your own last X messages in the current chat.",
        "usage": "{tr}purgeme <number_of_messages>",
    },
)
async def purge_my_messages(event):
    "Fast Self Message Purge"
    count_str = event.pattern_match.group(1).strip()
    try:
        count = int(count_str) if count_str else 5
    except ValueError:
        count = 5

    if count > 100:
        count = 100

    deleted = 0
    my_id = (await event.client.get_me()).id
    async for msg in event.client.iter_messages(event.chat_id, limit=count * 2):
        if msg.sender_id == my_id:
            await msg.delete()
            deleted += 1
            if deleted >= count:
                break

    temp = await event.client.send_message(
        event.chat_id, f"🗑️ `Purged {deleted} of your messages.`"
    )
    await asyncio.sleep(3)
    await temp.delete()


@catub.cat_cmd(
    pattern="selfdestruct(?:\\s|$)([\\s\\S]*)",
    command=("selfdestruct", plugin_category),
    info={
        "header": "Send a self-destructing message that deletes itself after X seconds.",
        "usage": "{tr}selfdestruct <seconds> <message>",
    },
)
async def self_destruct_msg(event):
    "Self Destructing Message"
    args = event.pattern_match.group(1).strip().split(maxsplit=1)
    if len(args) < 2:
        return await edit_delete(event, "`Usage: .selfdestruct <seconds> <message>`", 5)

    try:
        seconds = int(args[0])
    except ValueError:
        seconds = 10
    msg_text = args[1]

    for i in range(seconds, 0, -1):
        await event.edit(f"💣 **[Self-Destruct in {i}s]:**\n\n{msg_text}")
        await asyncio.sleep(1)

    await event.edit("💥 **BOOM! Message destroyed.**")
    await asyncio.sleep(1.5)
    await event.delete()
