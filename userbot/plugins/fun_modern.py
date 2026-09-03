import aiohttp
import io
import urllib.parse
from userbot import catub
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "fun"


@catub.cat_cmd(
    pattern="(crypto|coin)(?:\\s|$)([\\s\\S]*)",
    command=("crypto", plugin_category),
    info={
        "header": "Get live cryptocurrency price, 24h change and market data.",
        "usage": "{tr}crypto <symbol> (e.g. {tr}crypto btc, {tr}crypto sol, {tr}crypto eth)",
    },
)
async def crypto_price(event):
    "Live Crypto Price Tracker"
    coin = event.pattern_match.group(2).strip().lower()
    if not coin:
        coin = "btc"

    alias_map = {
        "btc": "bitcoin",
        "eth": "ethereum",
        "sol": "solana",
        "bnb": "binancecoin",
        "doge": "dogecoin",
        "xrp": "ripple",
        "ada": "cardano",
        "trx": "tron",
        "ton": "the-open-network",
        "shib": "shiba-inu",
        "pepe": "pepe",
        "near": "near",
        "avax": "avalanche-2",
        "link": "chainlink",
    }
    coin_id = alias_map.get(coin, coin)
    catevent = await edit_or_reply(event, f"`📈 Fetching data for {coin.upper()}...`")

    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd,inr,eur&include_24hr_change=true&include_market_cap=true"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if coin_id not in data:
                        return await catevent.edit(f"`Unknown crypto symbol: '{coin}'. Try btc, eth, sol, ton, doge...`")
                    cdata = data[coin_id]
                    usd = cdata.get("usd", 0)
                    inr = cdata.get("inr", 0)
                    eur = cdata.get("eur", 0)
                    change = cdata.get("usd_24h_change", 0)
                    change_emoji = "🟢 +" if change >= 0 else "🔴 "
                    mcap = cdata.get("usd_market_cap", 0)

                    msg = (
                        f"🪙 **{coin.upper()} / USD Price**\n\n"
                        f"💵 **USD:** `${usd:,.4f}`\n"
                        f"🇮🇳 **INR:** `₹{inr:,.2f}`\n"
                        f"💶 **EUR:** `€{eur:,.4f}`\n"
                        f"📊 **24h Change:** `{change_emoji}{change:.2f}%`\n"
                        f"🏦 **Market Cap:** `${mcap:,.0f}`"
                    )
                    await catevent.edit(msg)
                else:
                    await catevent.edit(f"`CoinGecko API returned HTTP {resp.status}`")
    except Exception as e:
        await catevent.edit(f"**Error fetching crypto price:** `{e}`")


@catub.cat_cmd(
    pattern="fake(?:\\s|$)([\\s\\S]*)",
    command=("fake", plugin_category),
    info={
        "header": "Generate a complete realistic fake identity for testing or form signups.",
        "usage": "{tr}fake (or {tr}fake us/in/de/fr)",
    },
)
async def fake_identity(event):
    "Generate Fake Profile"
    catevent = await edit_or_reply(event, "`👤 Generating fake identity...`")
    url = "https://randomuser.me/api/"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    u = res["results"][0]
                    name = f"{u['name']['title']} {u['name']['first']} {u['name']['last']}"
                    gender = u['gender'].capitalize()
                    dob = u['dob']['date'][:10]
                    age = u['dob']['age']
                    loc = u['location']
                    street = f"{loc['street']['number']} {loc['street']['name']}"
                    city = loc['city']
                    state = loc['state']
                    country = loc['country']
                    postcode = loc['postcode']
                    email = u['email']
                    username = u['login']['username']
                    phone = u['phone']
                    cell = u['cell']

                    msg = (
                        f"🎭 **Generated Fake Identity**\n\n"
                        f"👤 **Name:** `{name}` ({gender}, {age}yo)\n"
                        f"🎂 **DOB:** `{dob}`\n"
                        f"🏠 **Street:** `{street}`\n"
                        f"📍 **City/State:** `{city}, {state}`\n"
                        f"🌍 **Country:** `{country}` (`{postcode}`)\n"
                        f"📧 **Email:** `{email}`\n"
                        f"🔑 **Username:** `{username}`\n"
                        f"📱 **Phone:** `{phone}` | `{cell}`"
                    )
                    await catevent.edit(msg)
                else:
                    await catevent.edit("`Failed to generate identity!`")
    except Exception as e:
        await catevent.edit(f"`Error: {e}`")


@catub.cat_cmd(
    pattern="qr(?:\\s|$)([\\s\\S]*)",
    command=("qr", plugin_category),
    info={
        "header": "Generate a scannable QR Code image from any text or link.",
        "usage": "{tr}qr <text or url>",
    },
)
async def make_qr(event):
    "Generate QR Code Image"
    text = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not text and reply:
        text = reply.text
    if not text:
        return await edit_delete(event, "`Provide text or link to create a QR code!`", 5)

    catevent = await edit_or_reply(event, "`🔳 Generating QR Code...`")
    encoded = urllib.parse.quote(text)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=500x500&data={encoded}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(qr_url) as resp:
                if resp.status == 200:
                    img_bytes = await resp.read()
                    file_obj = io.BytesIO(img_bytes)
                    file_obj.name = "qrcode.png"
                    await catevent.delete()
                    await event.client.send_file(
                        event.chat_id,
                        file_obj,
                        caption=f"🔳 **QR Code for:**\n`{text}`",
                        reply_to=reply.id if reply else None,
                    )
                else:
                    await catevent.edit("`Failed to create QR code!`")
    except Exception as e:
        await catevent.edit(f"`QR Error: {e}`")


@catub.cat_cmd(
    pattern="ss(?:\\s|$)([\\s\\S]*)",
    command=("ss", plugin_category),
    info={
        "header": "Take a high-definition full screenshot of any website URL.",
        "usage": "{tr}ss <website url>",
    },
)
async def web_screenshot(event):
    "Capture Website Screenshot"
    url = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not url and reply:
        url = reply.text
    if not url:
        return await edit_delete(event, "`Provide a website URL! (e.g. .ss https://google.com)`", 5)

    if not url.startswith("http"):
        url = "https://" + url

    catevent = await edit_or_reply(event, f"`📸 Capturing screenshot of {url}...`")
    encoded = urllib.parse.quote(url)
    ss_api = f"https://image.thum.io/get/width/1280/crop/800/noanimate/{url}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ss_api, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    img_bytes = await resp.read()
                    file_obj = io.BytesIO(img_bytes)
                    file_obj.name = "screenshot.png"
                    await catevent.delete()
                    await event.client.send_file(
                        event.chat_id,
                        file_obj,
                        caption=f"📸 **Website Screenshot:**\n🔗 `{url}`",
                        reply_to=reply.id if reply else None,
                    )
                else:
                    await catevent.edit("`Could not capture screenshot of this site!`")
    except Exception as e:
        await catevent.edit(f"`Screenshot error: {e}`")


@catub.cat_cmd(
    pattern="short(?:\\s|$)([\\s\\S]*)",
    command=("short", plugin_category),
    info={
        "header": "Shorten long URLs into clean short links.",
        "usage": "{tr}short <url>",
    },
)
async def short_url(event):
    "Shorten URL"
    url = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not url and reply:
        url = reply.text
    if not url:
        return await edit_delete(event, "`Provide a URL to shorten!`", 5)

    catevent = await edit_or_reply(event, "`🔗 Shortening link...`")
    encoded = urllib.parse.quote(url)
    api = f"https://tinyurl.com/api-create.php?url={encoded}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api) as resp:
                if resp.status == 200:
                    short = await resp.text()
                    await catevent.edit(f"🔗 **Original:** `{url}`\n✂️ **Short Link:** {short}")
                else:
                    await catevent.edit("`Failed to shorten URL!`")
    except Exception as e:
        await catevent.edit(f"`Shortener error: {e}`")


@catub.cat_cmd(
    pattern="joke$",
    command=("joke", plugin_category),
    info={"header": "Fetch a random funny joke.", "usage": "{tr}joke"},
)
async def tell_joke(event):
    "Random Joke"
    catevent = await edit_or_reply(event, "`Fetching a joke...`")
    url = "https://official-joke-api.appspot.com/random_joke"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    j = await resp.json()
                    await catevent.edit(f"😂 **Joke:**\n\n{j['setup']}\n\n**{j['punchline']}** 🤣")
                else:
                    await catevent.edit("`No jokes right now!`")
    except Exception as e:
        await catevent.edit(f"`Error: {e}`")


@catub.cat_cmd(
    pattern="fact$",
    command=("fact", plugin_category),
    info={"header": "Fetch an interesting mind-blowing fact.", "usage": "{tr}fact"},
)
async def random_fact(event):
    "Random Fact"
    catevent = await edit_or_reply(event, "`Fetching a fact...`")
    url = "https://uselessfacts.jsph.pl/api/v2/facts/random"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    f = await resp.json()
                    await catevent.edit(f"💡 **Did You Know?**\n\n{f['text']}")
                else:
                    await catevent.edit("`Could not fetch fact!`")
    except Exception as e:
        await catevent.edit(f"`Error: {e}`")
