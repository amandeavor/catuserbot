import aiohttp
import base64
import hashlib
import json
import urllib.parse
from userbot import catub
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "ultroid"


@catub.cat_cmd(
    pattern="paste(?:\\s|$)([\\s\\S]*)",
    command=("paste", plugin_category),
    info={
        "header": "Upload text or code to a clean pastebin and get a shareable link.",
        "usage": "{tr}paste <text> (or reply to a message/file)",
    },
)
async def paste_text(event):
    "Upload Text to Pastebin"
    text = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not text and reply:
        if reply.text:
            text = reply.text
        elif reply.media:
            try:
                downloaded = await reply.download_media()
                with open(downloaded, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except Exception:
                pass

    if not text:
        return await edit_delete(event, "`Please provide text or reply to a message/file to paste!`", 5)

    catevent = await edit_or_reply(event, "`📋 Uploading to Pastebin...`")
    
    # Try dpaste.org / spacebin / pasty
    try:
        async with aiohttp.ClientSession() as session:
            data = {"content": text, "syntax": "text", "expiry_days": 7}
            async with session.post("https://dpaste.org/api/", data=data, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    paste_url = (await resp.text()).strip()
                    msg = (
                        f"📋 **Paste Successful!**\n\n"
                        f"🔗 **URL:** {paste_url}\n"
                        f"📄 **Raw:** {paste_url}/raw\n"
                        f"📊 **Characters:** `{len(text)}`"
                    )
                    return await catevent.edit(msg)
    except Exception:
        pass

    try:
        async with aiohttp.ClientSession() as session:
            payload = {"content": text}
            async with session.post("https://spaceb.in/api/v1/documents/", json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status in (200, 201):
                    res = await resp.json()
                    doc_id = res.get("payload", {}).get("id")
                    paste_url = f"https://spaceb.in/{doc_id}"
                    msg = (
                        f"📋 **Paste Successful!**\n\n"
                        f"🔗 **URL:** {paste_url}\n"
                        f"📊 **Characters:** `{len(text)}`"
                    )
                    return await catevent.edit(msg)
    except Exception as e:
        return await catevent.edit(f"`Failed to paste text: {e}`")

    await catevent.edit("`Could not reach pastebin services right now!`")


@catub.cat_cmd(
    pattern="cur(?:\\s|$)([\\s\\S]*)",
    command=("cur", plugin_category),
    info={
        "header": "Convert fiat currencies in real-time.",
        "usage": "{tr}cur <amount> <FROM> <TO> (e.g. {tr}cur 100 USD INR)",
    },
)
async def currency_converter(event):
    "Live Currency Converter"
    args = event.pattern_match.group(1).strip().split()
    if len(args) < 3:
        return await edit_delete(event, "`Usage: .cur <amount> <FROM> <TO> (e.g. .cur 100 USD INR)`", 5)

    try:
        amount = float(args[0])
    except ValueError:
        return await edit_delete(event, "`Amount must be a valid number!`", 5)

    from_curr = args[1].upper()
    to_curr = args[2].upper()

    catevent = await edit_or_reply(event, f"`💱 Converting {amount} {from_curr} to {to_curr}...`")
    url = f"https://open.er-api.com/v6/latest/{from_curr}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    rates = data.get("rates", {})
                    if to_curr not in rates:
                        return await catevent.edit(f"`Unknown currency code: '{to_curr}'`")
                    rate = rates[to_curr]
                    result = amount * rate
                    date = data.get("time_last_update_utc", "")[:16]

                    msg = (
                        f"💱 **Currency Exchange Rate:**\n\n"
                        f"💵 **Input:** `{amount:,.2f} {from_curr}`\n"
                        f"💰 **Converted:** `{result:,.2f} {to_curr}`\n\n"
                        f"📊 **Rate:** `1 {from_curr} = {rate:.4f} {to_curr}`\n"
                        f"⏰ **Updated:** `{date}`"
                    )
                    await catevent.edit(msg)
                else:
                    await catevent.edit(f"`Could not fetch rates for {from_curr}!`")
    except Exception as e:
        await catevent.edit(f"`Currency Error: {e}`")


@catub.cat_cmd(
    pattern="ud(?:\\s|$)([\\s\\S]*)",
    command=("ud", plugin_category),
    info={
        "header": "Search Urban Dictionary for slang definitions.",
        "usage": "{tr}ud <term>",
    },
)
async def urban_dict(event):
    "Urban Dictionary Search"
    term = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not term and reply and reply.text:
        term = reply.text.strip()
    if not term:
        return await edit_delete(event, "`Provide a slang word to lookup on Urban Dictionary!`", 5)

    catevent = await edit_or_reply(event, f"`📖 Searching Urban Dictionary for '{term}'...`")
    encoded = urllib.parse.quote(term)
    url = f"https://api.urbandictionary.com/v0/define?term={encoded}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("list", [])
                    if not results:
                        return await catevent.edit(f"`No definitions found for '{term}' on Urban Dictionary.`")

                    top = results[0]
                    word = top.get("word", term)
                    definition = top.get("definition", "").replace("[", "").replace("]", "")
                    example = top.get("example", "").replace("[", "").replace("]", "")
                    thumbs_up = top.get("thumbs_up", 0)
                    thumbs_down = top.get("thumbs_down", 0)

                    if len(definition) > 1000:
                        definition = definition[:1000] + "..."
                    if len(example) > 500:
                        example = example[:500] + "..."

                    msg = (
                        f"📚 **Urban Dictionary:** `{word}`\n\n"
                        f"📖 **Definition:**\n{definition}\n\n"
                        f"💬 **Example:**\n_{example}_\n\n"
                        f"👍 `{thumbs_up}` | 👎 `{thumbs_down}`"
                    )
                    await catevent.edit(msg)
                else:
                    await catevent.edit("`Urban Dictionary API returned error!`")
    except Exception as e:
        await catevent.edit(f"`UD Error: {e}`")


@catub.cat_cmd(
    pattern="dict(?:\\s|$)([\\s\\S]*)",
    command=("dict", plugin_category),
    info={
        "header": "Lookup Oxford English dictionary definitions and phonetics.",
        "usage": "{tr}dict <word>",
    },
)
async def dictionary_lookup(event):
    "English Dictionary Lookup"
    word = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not word and reply and reply.text:
        word = reply.text.strip()
    if not word:
        return await edit_delete(event, "`Provide a word to lookup!`", 5)

    catevent = await edit_or_reply(event, f"`📖 Searching dictionary for '{word}'...`")
    encoded = urllib.parse.quote(word)
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{encoded}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    entry = data[0]
                    w_name = entry.get("word", word).title()
                    phonetic = entry.get("phonetic", "")
                    meanings = entry.get("meanings", [])

                    msg = f"📖 **Dictionary:** `{w_name}` {f'({phonetic})' if phonetic else ''}\n\n"
                    for m in meanings[:2]:
                        part = m.get("partOfSpeech", "meaning")
                        defs = m.get("definitions", [])
                        if defs:
                            d_text = defs[0].get("definition", "")
                            example = defs[0].get("example", "")
                            msg += f"🔸 **{part.capitalize()}:** {d_text}\n"
                            if example:
                                msg += f"   _Example: \"{example}\"_\n"
                            msg += "\n"

                    await catevent.edit(msg.strip())
                else:
                    await catevent.edit(f"`Word '{word}' not found in dictionary!`")
    except Exception as e:
        await catevent.edit(f"`Dictionary Error: {e}`")


@catub.cat_cmd(
    pattern="country(?:\\s|$)([\\s\\S]*)",
    command=("country", plugin_category),
    info={
        "header": "Get deep facts, population, flag, and currency of any country.",
        "usage": "{tr}country <country_name>",
    },
)
async def country_intel(event):
    "Country Intelligence"
    country_name = event.pattern_match.group(1).strip()
    if not country_name:
        return await edit_delete(event, "`Provide a country name! (e.g. .country Japan or .country India)`", 5)

    catevent = await edit_or_reply(event, f"`🌍 Looking up country info for '{country_name}'...`")
    encoded = urllib.parse.quote(country_name)
    url = f"https://restcountries.com/v3.1/name/{encoded}?fullText=false"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    c = data[0]
                    name = c.get("name", {}).get("common", country_name)
                    official = c.get("name", {}).get("official", "")
                    flag = c.get("flag", "🏳️")
                    capital = ", ".join(c.get("capital", ["N/A"]))
                    region = f"{c.get('region', '')} ({c.get('subregion', '')})"
                    pop = c.get("population", 0)
                    area = c.get("area", 0)
                    currencies = list(c.get("currencies", {}).keys())
                    curr_str = ", ".join(currencies) if currencies else "N/A"
                    languages = list(c.get("languages", {}).values())
                    lang_str = ", ".join(languages) if languages else "N/A"
                    calling_code = c.get("idd", {}).get("root", "") + "".join(c.get("idd", {}).get("suffixes", [""])[:1])

                    msg = (
                        f"{flag} **{name}** ({official})\n\n"
                        f"🏛️ **Capital:** `{capital}`\n"
                        f"👥 **Population:** `{pop:,.0f}`\n"
                        f"🗺️ **Region:** `{region}`\n"
                        f"📐 **Area:** `{area:,.0f} km²`\n"
                        f"💵 **Currency:** `{curr_str}`\n"
                        f"🗣️ **Languages:** `{lang_str}`\n"
                        f"📞 **Calling Code:** `{calling_code}`"
                    )
                    await catevent.edit(msg)
                else:
                    await catevent.edit(f"`Country '{country_name}' not found!`")
    except Exception as e:
        await catevent.edit(f"`Country Error: {e}`")


@catub.cat_cmd(
    pattern="hash(?:\\s|$)([\\s\\S]*)",
    command=("hash", plugin_category),
    info={
        "header": "Calculate MD5, SHA1, SHA256, and SHA512 hashes of any text.",
        "usage": "{tr}hash <text>",
    },
)
async def generate_hashes(event):
    "Cryptographic Hash Generator"
    text = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not text and reply and reply.text:
        text = reply.text
    if not text:
        return await edit_delete(event, "`Provide text to hash!`", 5)

    md5_h = hashlib.md5(text.encode()).hexdigest()
    sha1_h = hashlib.sha1(text.encode()).hexdigest()
    sha256_h = hashlib.sha256(text.encode()).hexdigest()
    sha512_h = hashlib.sha512(text.encode()).hexdigest()

    msg = (
        f"🔐 **Cryptographic Hashes for:** `{text[:30]}`\n\n"
        f"🔹 **MD5:** `{md5_h}`\n"
        f"🔹 **SHA-1:** `{sha1_h}`\n"
        f"🔹 **SHA-256:** `{sha256_h}`\n"
        f"🔹 **SHA-512:** `{sha512_h[:64]}...`"
    )
    await edit_or_reply(event, msg)


@catub.cat_cmd(
    pattern="(b64e|b64d)(?:\\s|$)([\\s\\S]*)",
    command=("b64e", plugin_category),
    info={
        "header": "Encode or decode Base64 strings.",
        "usage": "{tr}b64e <text> or {tr}b64d <base64_string>",
    },
)
async def base64_codec(event):
    "Base64 Encoder / Decoder"
    cmd = event.pattern_match.group(1)
    text = event.pattern_match.group(2).strip()
    reply = await event.get_reply_message()
    if not text and reply and reply.text:
        text = reply.text.strip()
    if not text:
        return await edit_delete(event, "`Provide text to encode/decode!`", 5)

    try:
        if cmd == "b64e":
            encoded = base64.b64encode(text.encode()).decode()
            await edit_or_reply(event, f"🔒 **Base64 Encoded:**\n`{encoded}`")
        else:
            decoded = base64.b64decode(text.encode()).decode(errors="ignore")
            await edit_or_reply(event, f"🔓 **Base64 Decoded:**\n`{decoded}`")
    except Exception as e:
        await edit_or_reply(event, f"`Base64 Error: {e}`")
