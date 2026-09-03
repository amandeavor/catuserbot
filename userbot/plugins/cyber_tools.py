import aiohttp
import json
import random
import string
import urllib.parse
from userbot import catub
from ..core.managers import edit_or_reply, edit_delete

plugin_category = "cyber"

CURRENT_TEMPMAIL = {}


@catub.cat_cmd(
    pattern="tempmail$",
    command=("tempmail", plugin_category),
    info={
        "header": "Generate a disposable temporary email address for signups.",
        "usage": "{tr}tempmail (use {tr}checkmail to read OTPs)",
    },
)
async def generate_temp_mail(event):
    "Generate Temporary Disposable Email"
    catevent = await edit_or_reply(event, "`📬 Generating fresh disposable email...`")
    domain_url = "https://www.1secmail.com/api/v1/?action=getDomainList"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(domain_url) as resp:
                if resp.status == 200:
                    domains = await resp.json()
                    domain = random.choice(domains)
                    user = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
                    email_addr = f"{user}@{domain}"
                    CURRENT_TEMPMAIL["login"] = user
                    CURRENT_TEMPMAIL["domain"] = domain
                    CURRENT_TEMPMAIL["address"] = email_addr

                    msg = (
                        f"📧 **Temporary Disposable Email Created:**\n\n"
                        f"📬 ` {email_addr} `\n\n"
                        f"👉 Copy the email above for signups.\n"
                        f"👉 When you need your OTP or confirmation link, send: `.checkmail`"
                    )
                    await catevent.edit(msg)
                else:
                    await catevent.edit("`Failed to reach email service!`")
    except Exception as e:
        await catevent.edit(f"`Tempmail error: {e}`")


@catub.cat_cmd(
    pattern="checkmail$",
    command=("checkmail", plugin_category),
    info={
        "header": "Check inbox for received OTPs and verification emails.",
        "usage": "{tr}checkmail",
    },
)
async def check_temp_mail(event):
    "Check Disposable Email Inbox"
    if "login" not in CURRENT_TEMPMAIL:
        return await edit_delete(event, "`No active tempmail found! Create one with .tempmail first.`", 5)

    user = CURRENT_TEMPMAIL["login"]
    domain = CURRENT_TEMPMAIL["domain"]
    email_addr = CURRENT_TEMPMAIL["address"]

    catevent = await edit_or_reply(event, f"`🔍 Checking inbox for {email_addr}...`")
    inbox_url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={user}&domain={domain}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(inbox_url) as resp:
                if resp.status == 200:
                    messages = await resp.json()
                    if not messages:
                        return await catevent.edit(f"📭 **Inbox is currently empty for:**\n`{email_addr}`\n\n*(Send OTP and try `.checkmail` again in 10s)*")

                    msg_out = f"📬 **Inbox for `{email_addr}` ({len(messages)} message(s)):**\n\n"
                    for m in messages[:3]:
                        msg_id = m["id"]
                        msg_detail_url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={user}&domain={domain}&id={msg_id}"
                        async with session.get(msg_detail_url) as d_resp:
                            if d_resp.status == 200:
                                d = await d_resp.json()
                                from_who = d.get("from", "Unknown")
                                subject = d.get("subject", "(No Subject)")
                                body = d.get("textBody", "").strip()[:500]
                                msg_out += f"👤 **From:** `{from_who}`\n📌 **Subject:** `{subject}`\n📝 **Content:**\n`{body}`\n\n---\n\n"

                    await catevent.edit(msg_out)
                else:
                    await catevent.edit("`Could not fetch inbox messages!`")
    except Exception as e:
        await catevent.edit(f"`Checkmail error: {e}`")


@catub.cat_cmd(
    pattern="ip(?:\\s|$)([\\s\\S]*)",
    command=("ip", plugin_category),
    info={
        "header": "Lookup detailed geolocation, ISP, ASN and timezone of an IP or Domain.",
        "usage": "{tr}ip <ip or domain> (e.g. {tr}ip 1.1.1.1 or {tr}ip google.com)",
    },
)
async def ip_lookup(event):
    "IP & Domain Geolocation Lookup"
    target = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not target and reply and reply.text:
        target = reply.text.strip()
    if not target:
        target = ""

    catevent = await edit_or_reply(event, f"`🌐 Looking up IP intelligence for '{target or 'my server'}'...`")
    url = f"http://ip-api.com/json/{target}?fields=status,message,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,as,query"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") != "success":
                        return await catevent.edit(f"`Lookup failed: {data.get('message', 'Invalid target')}`")

                    ip = data.get("query", target)
                    country = data.get("country", "Unknown")
                    code = data.get("countryCode", "")
                    city = data.get("city", "Unknown")
                    region = data.get("regionName", "Unknown")
                    zipcode = data.get("zip", "Unknown")
                    tz = data.get("timezone", "Unknown")
                    isp = data.get("isp", "Unknown")
                    org = data.get("org", "Unknown")
                    asn = data.get("as", "Unknown")
                    lat = data.get("lat", 0)
                    lon = data.get("lon", 0)

                    msg = (
                        f"🌐 **IP Geolocation Intelligence:**\n\n"
                        f"🎯 **IP Address:** `{ip}`\n"
                        f"🌍 **Country:** `{country}` (`{code}`)\n"
                        f"📍 **City/Region:** `{city}, {region}` (`{zipcode}`)\n"
                        f"⏰ **Timezone:** `{tz}`\n"
                        f"🏢 **ISP:** `{isp}`\n"
                        f"💼 **Organization:** `{org}`\n"
                        f"🔢 **ASN:** `{asn}`\n"
                        f"🗺️ **Coordinates:** `{lat}, {lon}`"
                    )
                    await catevent.edit(msg)
                else:
                    await catevent.edit("`IP API returned an error!`")
    except Exception as e:
        await catevent.edit(f"`IP Lookup error: {e}`")


@catub.cat_cmd(
    pattern="lyrics(?:\\s|$)([\\s\\S]*)",
    command=("lyrics", plugin_category),
    info={
        "header": "Search and display full synchronized song lyrics.",
        "usage": "{tr}lyrics <song title>",
    },
)
async def fetch_lyrics(event):
    "Fetch Song Lyrics"
    song = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not song and reply and reply.text:
        song = reply.text.strip()
    if not song:
        return await edit_delete(event, "`Provide a song title to fetch lyrics!`", 5)

    catevent = await edit_or_reply(event, f"`🎵 Searching lyrics for '{song}'...`")
    encoded = urllib.parse.quote(song)
    url = f"https://some-random-api.com/lyrics?title={encoded}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    title = data.get("title", song)
                    author = data.get("author", "Unknown")
                    lyrics = data.get("lyrics", "No lyrics available.")
                    if len(lyrics) > 3800:
                        lyrics = lyrics[:3800] + "\n\n...(truncated)"

                    msg = f"🎶 **Lyrics for:** `{title}` - `{author}`\n\n{lyrics}"
                    await catevent.edit(msg)
                else:
                    await catevent.edit(f"`Could not find lyrics for '{song}'!`")
    except Exception as e:
        await catevent.edit(f"`Lyrics error: {e}`")


@catub.cat_cmd(
    pattern="weather(?:\\s|$)([\\s\\S]*)",
    command=("weather", plugin_category),
    info={
        "header": "Display comprehensive real-time weather information.",
        "usage": "{tr}weather <city name>",
    },
)
async def live_weather(event):
    "Live Weather Report"
    city = event.pattern_match.group(1).strip()
    if not city:
        city = "London"

    catevent = await edit_or_reply(event, f"`🌤️ Fetching weather for '{city}'...`")
    encoded = urllib.parse.quote(city)
    url = f"https://wttr.in/{encoded}?format=j1"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    curr = data["current_condition"][0]
                    temp_c = curr.get("temp_C")
                    temp_f = curr.get("temp_F")
                    feels_c = curr.get("FeelsLikeC")
                    desc = curr.get("weatherDesc", [{}])[0].get("value", "Clear")
                    humidity = curr.get("humidity")
                    wind_kmph = curr.get("windspeedKmph")
                    uv = curr.get("uvIndex")

                    msg = (
                        f"🌤️ **Weather Report for {city.title()}**\n\n"
                        f"🌡️ **Temperature:** `{temp_c}°C` (`{temp_f}°F`)\n"
                        f"🤔 **Feels Like:** `{feels_c}°C`\n"
                        f"☁️ **Condition:** `{desc}`\n"
                        f"💧 **Humidity:** `{humidity}%`\n"
                        f"💨 **Wind Speed:** `{wind_kmph} km/h`\n"
                        f"☀️ **UV Index:** `{uv}`"
                    )
                    await catevent.edit(msg)
                else:
                    await catevent.edit(f"`Could not find city '{city}'!`")
    except Exception as e:
        await catevent.edit(f"`Weather error: {e}`")
