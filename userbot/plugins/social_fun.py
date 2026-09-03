import asyncio
import random
from userbot import catub
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "fun"


@catub.cat_cmd(
    pattern="type(?:\\s|$)([\\s\\S]*)",
    command=("type", plugin_category),
    info={
        "header": "Animated typewriter typing effect in chat.",
        "usage": "{tr}type <your message>",
    },
)
async def typewriter_effect(event):
    "Typewriter Animation"
    text = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not text and reply and reply.text:
        text = reply.text.strip()
    if not text:
        return await edit_delete(event, "`Provide a sentence to type!`", 5)

    typing_symbol = "▌"
    current_text = ""
    for char in text:
        current_text += char
        try:
            await event.edit(current_text + typing_symbol)
            await asyncio.sleep(0.08)
        except Exception:
            pass
    await event.edit(current_text)


@catub.cat_cmd(
    pattern="mock(?:\\s|$)([\\s\\S]*)",
    command=("mock", plugin_category),
    info={
        "header": "Convert text into mOcKiNg SpOnGeBoB format.",
        "usage": "{tr}mock <text> (or reply to text)",
    },
)
async def mock_text(event):
    "Mock Text"
    text = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not text and reply and reply.text:
        text = reply.text.strip()
    if not text:
        return await edit_delete(event, "`Provide text to mock!`", 5)

    mocked = "".join(
        c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(text)
    )
    await event.edit(f"{mocked} 🐔")


@catub.cat_cmd(
    pattern="flip(?:\\s|$)([\\s\\S]*)",
    command=("flip", plugin_category),
    info={
        "header": "Flip text upside down.",
        "usage": "{tr}flip <text>",
    },
)
async def flip_upside_down(event):
    "Flip Text"
    text = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not text and reply and reply.text:
        text = reply.text.strip()
    if not text:
        return await edit_delete(event, "`Provide text to flip!`", 5)

    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890,.?!'\""
    flipped = "ɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz∀qƆpƎℲפHIſʞ˥WNOԀQɹS┴∩ΛMX⅄ZƖᄅƐㄣϛ9ㄥ860'˙¿¡,„"
    table = str.maketrans(normal, flipped)
    res = text.translate(table)[::-1]
    await event.edit(f"(╯°□°)╯︵ {res}")


@catub.cat_cmd(
    pattern="love(?:\\s|$)([\\s\\S]*)",
    command=("love", plugin_category),
    info={
        "header": "Calculate love compatibility between two names.",
        "usage": "{tr}love <name1> <name2>",
    },
)
async def love_calc(event):
    "Love Calculator"
    args = event.pattern_match.group(1).strip().split()
    if len(args) < 2:
        return await edit_delete(event, "`Usage: .love <Name1> <Name2>`", 5)

    n1, n2 = args[0], args[1]
    # Deterministic hash for consistent fun results
    combined = (n1.lower() + n2.lower())
    score = sum(ord(c) for c in combined) % 101

    filled = int(score / 10)
    bar = "💖" * filled + "🖤" * (10 - filled)

    if score > 85:
        msg = "💍 Soulmates! Made for each other!"
    elif score > 60:
        msg = "🔥 Strong bond and great chemistry!"
    elif score > 40:
        msg = "⚡ Good friends with some sparks."
    else:
        msg = "💀 Danger zone... Run away!"

    res = (
        f"💘 **Love Compatibility Test**\n\n"
        f"👤 `{n1.title()}` + 👤 `{n2.title()}`\n\n"
        f"📊 **Score:** `{score}%`\n"
        f"[{bar}]\n\n"
        f"💬 **Verdict:** {msg}"
    )
    await event.edit(res)


@catub.cat_cmd(
    pattern="(dice|dart|basket|slot|football)$",
    command=("dice", plugin_category),
    info={
        "header": "Roll animated Telegram interactive emojis.",
        "usage": "{tr}dice, {tr}dart, {tr}basket, {tr}slot, {tr}football",
    },
)
async def interactive_game(event):
    "Interactive Animated Emojis"
    cmd = event.pattern_match.group(1)
    emoji_map = {
        "dice": "🎲",
        "dart": "🎯",
        "basket": "🏀",
        "slot": "🎰",
        "football": "⚽",
    }
    emoji = emoji_map.get(cmd, "🎲")
    await event.delete()
    await event.client.send_file(event.chat_id, emoji)
