import aiohttp
import io
import json
import os
import urllib.parse
from userbot import catub
from ..Config import Config
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "ai"


async def query_ai(prompt: str) -> str:
    """Universal resilient AI query engine with multi-tier fallback."""
    # Tier 1: Google Gemini API (if key is set in Render Env)
    gemini_key = os.environ.get("GEMINI_API_KEY") or getattr(Config, "GEMINI_API_KEY", None)
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            pass

    # Tier 2: OpenAI API (if key is set in Render Env)
    openai_key = os.environ.get("OPENAI_API_KEY") or getattr(Config, "OPENAI_API_KEY", None)
    if openai_key:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
        except Exception:
            pass

    # Tier 3: Free Keyless Multi-Provider Endpoints
    free_endpoints = [
        # Provider A: Open Text Router
        ("https://text.pollinations.ai/openai/" + urllib.parse.quote(prompt[:300]), None, "get"),
        # Provider B: PopCat fallback
        ("https://api.popcat.xyz/chatbot?msg=" + urllib.parse.quote(prompt[:200]), None, "popcat"),
        # Provider C: DuckDuckGo instant summary
        ("https://api.duckduckgo.com/?q=" + urllib.parse.quote(prompt) + "&format=json&no_html=1&skip_disambig=1", None, "ddg"),
    ]

    async with aiohttp.ClientSession() as session:
        for url, payload, p_type in free_endpoints:
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                if p_type == "get":
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            if len(text.strip()) > 5:
                                return text.strip()
                elif p_type == "popcat":
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            ans = data.get("response")
                            if ans and ans != "Timed Out":
                                return ans
                elif p_type == "ddg":
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            ans = data.get("AbstractText") or data.get("Answer")
                            if ans:
                                return ans
            except Exception:
                continue

    return "Could not retrieve AI response at this moment. You can also add a free `GEMINI_API_KEY` to Render Environment Variables for 100% instant Google Gemini responses!"


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
