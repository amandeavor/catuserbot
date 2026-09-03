import aiohttp
import io
import json
import os
import urllib.parse
from userbot import catub
from ..Config import Config
from ..core.managers import edit_or_reply, edit_delete
from ..sql_helper.globals import addgvar, gvarstatus

plugin_category = "ai"


def get_gemini_key():
    """Retrieve Gemini API key from database or environment variables."""
    key = (
        gvarstatus("GEMINI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GEMINI_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or getattr(Config, "GEMINI_API_KEY", None)
    )
    if key:
        return str(key).strip().strip('"').strip("'")
    return None


async def query_ai(prompt: str) -> str:
    """Universal resilient AI query engine with Gemini and clear error handling."""
    gemini_key = get_gemini_key()
    if not gemini_key:
        return (
            "⚠️ **Gemini API Key is not set yet.**\n\n"
            "👉 Just send this command in Telegram:\n"
            "`.setgemini <your_API_key>`\n\n"
            "*(Get your 100% free key at https://aistudio.google.com)*"
        )

    models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
    last_err = ""
    for m in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={gemini_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]
                    else:
                        err_text = await resp.text()
                        last_err = f"HTTP {resp.status}: {err_text[:200]}"
        except Exception as e:
            last_err = str(e)
            continue

    return f"❌ **Google Gemini Error:** `{last_err}`\n\n*Check your key or update it with `.setgemini <key>` in Telegram.*"


@catub.cat_cmd(
    pattern="setgemini(?:\\s|$)([\\s\\S]*)",
    command=("setgemini", plugin_category),
    info={
        "header": "Set your Google Gemini API key directly from Telegram.",
        "usage": "{tr}setgemini <your_api_key>",
    },
)
async def set_gemini_key(event):
    "Save Gemini API Key"
    key = event.pattern_match.group(1).strip()
    if not key:
        return await edit_delete(event, "`Usage: .setgemini <your_api_key_from_aistudio.google.com>`", 5)

    clean_key = key.strip().strip('"').strip("'")
    addgvar("GEMINI_API_KEY", clean_key)
    await edit_or_reply(
        event,
        "✅ **Google Gemini API Key has been saved successfully to your database!**\n\n"
        "🚀 Now try asking anything: `.ai hello what can you do?`"
    )


@catub.cat_cmd(
    pattern="checkgemini$",
    command=("checkgemini", plugin_category),
    info={"header": "Check if Gemini API Key is configured.", "usage": "{tr}checkgemini"},
)
async def check_gemini_key(event):
    "Check Gemini API Status"
    key = get_gemini_key()
    if key:
        masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"
        await edit_or_reply(event, f"🟢 **Gemini API Key is ACTIVE:** `{masked}`")
    else:
        await edit_or_reply(event, "🔴 **No Gemini API Key found.**\nSet it using: `.setgemini <key>`")


@catub.cat_cmd(
    pattern="(ai|ask|gpt|gemini)(?:\\s|$)([\\s\\S]*)",
    command=("ai", plugin_category),
    info={
        "header": "Ask AI anything with deep reasoning and clean formatting.",
        "usage": "{tr}ai <query> or reply to message with {tr}ai",
    },
)
async def ai_chat(event):
    "Universal AI Chat Assistant"
    query = event.pattern_match.group(2).strip()
    reply = await event.get_reply_message()
    if not query and reply and reply.text:
        query = reply.text.strip()
    if not query:
        return await edit_delete(event, "`Please provide a prompt or question for the AI!`", 5)

    catevent = await edit_or_reply(event, "`🧠 Thinking...`")
    answer = await query_ai(query)

    formatted = f"💡 **Question:** `{query}`\n\n**🤖 AI:**\n{answer}"
    if len(formatted) > 4096:
        formatted = formatted[:4090] + "..."
    await catevent.edit(formatted)


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
    summary = await query_ai(prompt)
    await catevent.edit(f"📑 **Summary:**\n\n{summary}")


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
    corrected = await query_ai(prompt)
    await catevent.edit(f"✍️ **Corrected:**\n\n{corrected}")


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
    res = await query_ai(prompt)
    await catevent.edit(f"🍼 **ELI5: {topic}**\n\n{res}")
