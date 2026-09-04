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
    pattern="raidlock(?:\\s|$)([\\s\\S]*)",
    command=("raidlock", plugin_category),
    info={
        "header": "Lock down group permissions during a raid or attack.",
        "usage": "{tr}raidlock <on/off>",
    },
)
async def raid_lock_chat(event):
    "Emergency Raid Lock"
    if event.is_private:
        return await edit_delete(event, "`This command can only be used in groups!`", 5)

    input_str = event.pattern_match.group(1).strip().lower()
    if input_str not in ("on", "off"):
        return await edit_delete(event, "`Usage: .raidlock <on/off>`", 5)

    catevent = await edit_or_reply(event, f"`Engaging raid defense mode: {input_str}...`")
    from telethon.tl.types import ChatBannedRights
    from telethon.tl.functions.messages import EditChatDefaultBannedRightsRequest

    if input_str == "on":
        rights = ChatBannedRights(
            until_date=None,
            send_messages=True,
            send_media=True,
            send_stickers=True,
            send_gifs=True,
            send_games=True,
            send_inline=True,
            embed_links=True,
            send_polls=True,
            invite_users=True,
            pin_messages=True,
            change_info=True,
        )
        msg = "🚨 **Raid Lock Engaged!** Default permissions restricted."
    else:
        rights = ChatBannedRights(
            until_date=None,
            send_messages=False,
            send_media=False,
            send_stickers=False,
            send_gifs=False,
            send_games=False,
            send_inline=False,
            embed_links=False,
            send_polls=False,
            invite_users=False,
            pin_messages=True,
            change_info=True,
        )
        msg = "✅ **Raid Lock Disengaged.** Default permissions restored."

    try:
        await event.client(
            EditChatDefaultBannedRightsRequest(peer=event.chat_id, banned_rights=rights)
        )
        await catevent.edit(msg)
    except Exception as e:
        await catevent.edit(f"❌ **Failed to set raid lock:** `{e}`")
