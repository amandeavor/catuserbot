import asyncio
from telethon.tl.types import ChannelParticipantsKicked
from userbot import catub
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "admin"


@catub.cat_cmd(
    pattern="(kickdeleted|zombies)$",
    command=("kickdeleted", plugin_category),
    info={
        "header": "Clean up group by kicking all deleted/ghost accounts.",
        "usage": "{tr}kickdeleted",
    },
)
async def kick_deleted_accounts(event):
    "Kick All Deleted Accounts"
    if event.is_private:
        return await edit_delete(event, "`This command can only be used in groups!`", 5)

    catevent = await edit_or_reply(event, "`🔍 Scanning for deleted ghost accounts...`")
    kicked_count = 0
    del_users = []

    async for user in event.client.iter_participants(event.chat_id):
        if user.deleted:
            del_users.append(user)

    if not del_users:
        return await catevent.edit("✅ **No deleted accounts found in this group!**")

    await catevent.edit(f"`Found {len(del_users)} deleted accounts. Cleaning up...`")
    for user in del_users:
        try:
            await event.client.kick_participant(event.chat_id, user.id)
            kicked_count += 1
            await asyncio.sleep(0.3)
        except Exception:
            pass

    await catevent.edit(f"🧹 **Successfully kicked `{kicked_count}` deleted accounts from group!**")


@catub.cat_cmd(
    pattern="fakeaction(?:\\s|$)([\\s\\S]*)",
    command=("fakeaction", plugin_category),
    info={
        "header": "Simulate continuous typing or media recording action in a chat.",
        "usage": "{tr}fakeaction <typing|audio|video|photo|document|game|cancel>",
    },
)
async def fake_chat_action(event):
    "Simulate Chat Action"
    action = event.pattern_match.group(1).strip().lower()
    valid_actions = {
        "typing": "typing",
        "audio": "record-audio",
        "video": "record-video",
        "photo": "upload-photo",
        "document": "upload-document",
        "game": "game",
    }

    if action not in valid_actions:
        return await edit_delete(
            event, f"`Valid actions: {', '.join(valid_actions.keys())}`", 5
        )

    await event.delete()
    # Send action for 15 seconds
    async with event.client.action(event.chat_id, valid_actions[action]):
        await asyncio.sleep(15)


@catub.cat_cmd(
    pattern="delayspam(?:\\s|$)([\\s\\S]*)",
    command=("delayspam", plugin_category),
    info={
        "header": "Spam messages with custom delay.",
        "usage": "{tr}delayspam <count> <delay_seconds> <message>",
    },
)
async def delay_spam_msgs(event):
    "Delay Spammer"
    args = event.pattern_match.group(1).strip().split(maxsplit=2)
    if len(args) < 3:
        return await edit_delete(event, "`Usage: .delayspam <count> <delay_seconds> <message>`", 5)

    try:
        count = int(args[0])
        delay = float(args[1])
    except ValueError:
        return await edit_delete(event, "`Count and delay must be numbers!`", 5)

    msg = args[2]
    await event.delete()

    for _ in range(min(count, 50)):
        await event.client.send_message(event.chat_id, msg)
        await asyncio.sleep(delay)
