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
        "header": "Ask AI anything with deep reasoning and clean formatting.",
        "usage": "{tr}ai <query> or reply to message with {tr}ai",
    },
)
async def ai_chat(event):
    "Free AI Chat Assistant"
    query = event.pattern_match.group(2).strip()
    reply = await event.get_reply_message()
    if not query and reply and reply.text:
        query = reply.text.strip()
    if not query:
        return await edit_delete(event, "`Please provide a prompt or question for the AI!`", 5)

    catevent = await edit_or_reply(event, "`🧠 Thinking...`")
    encoded_prompt = urllib.parse.quote(query)
    url = f"https://text.pollinations.ai/{encoded_prompt}?model=openai&system=You+are+an+ultra-intelligent+helpful+AI+assistant.+Format+answers+concisely+with+markdown."

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=45)) as resp:
                if resp.status == 200:
                    answer = await resp.text()
                    formatted = f"💡 **Question:** `{query}`\n\n**🤖 AI:**\n{answer}"
                    if len(formatted) > 4096:
                        formatted = formatted[:4090] + "..."
                    await catevent.edit(formatted)
                else:
                    await catevent.edit(f"`AI Engine returned HTTP {resp.status}`")
    except Exception as e:
        await catevent.edit(f"**Error querying AI:** `{e}`")


@catub.cat_cmd(
    pattern="(imagine|flux|draw|gen|pic)(?:\\s|$)([\\s\\S]*)",
    command=("imagine", plugin_category),
    info={
        "header": "Generate ultra-HD AI images from text prompts (Flux / Photorealistic / 3D).",
        "usage": "{tr}imagine <prompt>",
    },
)
async def ai_image_gen(event):
    "Generate Ultra-HD AI Image"
    query = event.pattern_match.group(2).strip()
    reply = await event.get_reply_message()
    if not query and reply and reply.text:
        query = reply.text.strip()
    if not query:
        return await edit_delete(event, "`Please provide an image prompt! (e.g. .imagine cybernetic wolf in neon forest)`", 5)

    catevent = await edit_or_reply(event, f"`🎨 Rendering Flux 1.0 Ultra image: '{query}'...`")
    encoded_prompt = urllib.parse.quote(query)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    img_bytes = await resp.read()
                    file_obj = io.BytesIO(img_bytes)
                    file_obj.name = "flux_artwork.jpg"
                    await catevent.delete()
                    await event.client.send_file(
                        event.chat_id,
                        file_obj,
                        caption=f"✨ **Prompt:** `{query}`\n🎨 **Engine:** `Flux 1.0 Ultra-HD`",
                        reply_to=reply.id if reply else None,
                    )
                else:
                    await catevent.edit(f"`Failed to render image: HTTP {resp.status}`")
    except Exception as e:
        await catevent.edit(f"**Image Generation Error:** `{e}`")


@catub.cat_cmd(
    pattern="(anime|waifu)(?:\\s|$)([\\s\\S]*)",
    command=("anime", plugin_category),
    info={
        "header": "Generate beautiful anime style AI art.",
        "usage": "{tr}anime <prompt>",
    },
)
async def ai_anime_gen(event):
    "Generate Anime AI Art"
    query = event.pattern_match.group(2).strip()
    if not query:
        query = "beautiful anime scenery studio ghibli masterpiece"

    catevent = await edit_or_reply(event, f"`🌸 Rendering Anime Art: '{query}'...`")
    full_prompt = f"anime style masterpiece, high quality, vibrant, {query}"
    encoded = urllib.parse.quote(full_prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    img_bytes = await resp.read()
                    file_obj = io.BytesIO(img_bytes)
                    file_obj.name = "anime_art.jpg"
                    await catevent.delete()
                    await event.client.send_file(
                        event.chat_id,
                        file_obj,
                        caption=f"🌸 **Anime Art:** `{query}`",
                    )
                else:
                    await catevent.edit("`Failed to render anime art!`")
    except Exception as e:
        await catevent.edit(f"`Anime Art error: {e}`")


@catub.cat_cmd(
    pattern="summarize(?:\\s|$)([\\s\\S]*)",
    command=("summarize", plugin_category),
    info={
        "header": "Summarize long messages, articles, or text into key bullet points.",
        "usage": "{tr}summarize (reply to text)",
    },
)
async def ai_summarize(event):
    "Summarize Text with AI"
    reply = await event.get_reply_message()
    text = event.pattern_match.group(1).strip()
    if not text and reply and reply.text:
        text = reply.text
    if not text:
        return await edit_delete(event, "`Reply to a long message or provide text to summarize!`", 5)

    catevent = await edit_or_reply(event, "`📑 Summarizing...`")
    prompt = f"Summarize this text into 3-5 concise, high-impact bullet points:\n\n{text}"
    encoded = urllib.parse.quote(prompt)
    url = f"https://text.pollinations.ai/{encoded}?model=openai"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    summary = await resp.text()
                    await catevent.edit(f"📑 **Summary:**\n\n{summary}")
                else:
                    await catevent.edit("`Could not summarize text!`")
    except Exception as e:
        await catevent.edit(f"`Error: {e}`")


@catub.cat_cmd(
    pattern="grammar(?:\\s|$)([\\s\\S]*)",
    command=("grammar", plugin_category),
    info={
        "header": "Correct grammar, spelling, and re-write text professionally.",
        "usage": "{tr}grammar (reply to text or provide text)",
    },
)
async def ai_grammar(event):
    "Fix Grammar & Polish Text"
    reply = await event.get_reply_message()
    text = event.pattern_match.group(1).strip()
    if not text and reply and reply.text:
        text = reply.text
    if not text:
        return await edit_delete(event, "`Provide text or reply to a message to fix grammar!`", 5)

    catevent = await edit_or_reply(event, "`✍️ Polishing text...`")
    prompt = f"Fix all spelling, punctuation, and grammar mistakes in this text and make it sound natural and fluent. Output only the corrected text:\n\n{text}"
    encoded = urllib.parse.quote(prompt)
    url = f"https://text.pollinations.ai/{encoded}?model=openai"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    corrected = await resp.text()
                    await catevent.edit(f"✍️ **Corrected:**\n\n{corrected}")
                else:
                    await catevent.edit("`Failed to polish grammar!`")
    except Exception as e:
        await catevent.edit(f"`Error: {e}`")


@catub.cat_cmd(
    pattern="eli5(?:\\s|$)([\\s\\S]*)",
    command=("eli5", plugin_category),
    info={
        "header": "Explain complex topics like I am 5 years old.",
        "usage": "{tr}eli5 <topic>",
    },
)
async def ai_eli5(event):
    "Explain Like I'm 5"
    topic = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not topic and reply and reply.text:
        topic = reply.text
    if not topic:
        return await edit_delete(event, "`Provide a topic to explain! (e.g. .eli5 black holes)`", 5)

    catevent = await edit_or_reply(event, f"`🍼 Explaining '{topic}' in simple terms...`")
    prompt = f"Explain '{topic}' simply and clearly as if explaining to a 5-year-old child. Use easy analogies."
    encoded = urllib.parse.quote(prompt)
    url = f"https://text.pollinations.ai/{encoded}?model=openai"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    res = await resp.text()
                    await catevent.edit(f"🍼 **ELI5: {topic}**\n\n{res}")
                else:
                    await catevent.edit("`Could not generate explanation!`")
    except Exception as e:
        await catevent.edit(f"`Error: {e}`")
