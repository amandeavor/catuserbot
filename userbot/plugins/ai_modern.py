import aiohttp
import io
import urllib.parse
from userbot import catub
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "ai"


@catub.cat_cmd(
    pattern="(ai|ask|gpt)(?:\\s|$)([\\s\\S]*)",
    command=("ai", plugin_category),
    info={
        "header": "Ask AI anything (Free instant smart model).",
        "usage": "{tr}ai <query> or reply to message with {tr}ai",
    },
)
async def ai_chat(event):
    "Free AI Chat Assistant"
    query = event.pattern_match.group(2)
    reply = await event.get_reply_message()
    if not query and reply and reply.text:
        query = reply.text
    if not query:
        return await edit_delete(event, "`Please provide a prompt or question for the AI!`", 5)

    catevent = await edit_or_reply(event, "`🤖 AI is thinking...`")
    encoded_prompt = urllib.parse.quote(query)
    url = f"https://text.pollinations.ai/{encoded_prompt}?model=openai&system=You+are+a+helpful+and+smart+AI+assistant."

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=45)) as resp:
                if resp.status == 200:
                    answer = await resp.text()
                    formatted = f"**🧠 Prompt:** `{query}`\n\n**🤖 AI Response:**\n{answer}"
                    if len(formatted) > 4096:
                        formatted = formatted[:4090] + "..."
                    await catevent.edit(formatted)
                else:
                    await catevent.edit(f"`AI API returned status code: {resp.status}`")
    except Exception as e:
        await catevent.edit(f"**Error querying AI:** `{e}`")


@catub.cat_cmd(
    pattern="(imagine|flux|draw|gen)(?:\\s|$)([\\s\\S]*)",
    command=("imagine", plugin_category),
    info={
        "header": "Generate ultra-HD AI images from text prompt.",
        "usage": "{tr}imagine <detailed prompt>",
    },
)
async def ai_image(event):
    "Generate AI image using Flux/SD"
    query = event.pattern_match.group(2)
    reply = await event.get_reply_message()
    if not query and reply and reply.text:
        query = reply.text
    if not query:
        return await edit_delete(event, "`Please provide a prompt to generate an image!`", 5)

    catevent = await edit_or_reply(event, f"`🎨 Generating image for: '{query}'...`")
    encoded_prompt = urllib.parse.quote(query)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    img_bytes = await resp.read()
                    file_obj = io.BytesIO(img_bytes)
                    file_obj.name = "ai_image.jpg"
                    await catevent.delete()
                    await event.client.send_file(
                        event.chat_id,
                        file_obj,
                        caption=f"🎨 **Prompt:** `{query}`\n✨ **Model:** `Flux 1.0 Ultra`",
                        reply_to=reply.id if reply else None,
                    )
                else:
                    await catevent.edit(f"`Failed to generate image: HTTP {resp.status}`")
    except Exception as e:
        await catevent.edit(f"**Error generating AI image:** `{e}`")


@catub.cat_cmd(
    pattern="roast(?:\\s|$)([\\s\\S]*)",
    command=("roast", plugin_category),
    info={
        "header": "Roast a user or their message with ruthless AI humor.",
        "usage": "{tr}roast (reply to user or provide text)",
    },
)
async def ai_roast(event):
    "Roast a user or text using AI"
    query = event.pattern_match.group(1)
    reply = await event.get_reply_message()
    target_text = ""
    if reply:
        target_text = reply.text or "this user"
    elif query:
        target_text = query
    else:
        target_text = "someone who has no comeback"

    catevent = await edit_or_reply(event, "`🔥 Cooking up a roast...`")
    prompt = f"Write a funny, witty, savage 2-sentence roast about: {target_text}. Keep it playful and humorous."
    encoded = urllib.parse.quote(prompt)
    url = f"https://text.pollinations.ai/{encoded}?model=openai"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    roast = await resp.text()
                    await catevent.edit(f"🔥 **Roast:**\n\n{roast}")
                else:
                    await catevent.edit("`Couldn't roast right now!`")
    except Exception as e:
        await catevent.edit(f"`Roast error: {e}`")
