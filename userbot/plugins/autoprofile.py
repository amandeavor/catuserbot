# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.

# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement".

# Please see: https://github.com/TgCatUB/catuserbot/blob/master/LICENSE
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Special Credits: @Nihinivi for batmanpfp and thorpfp

import asyncio
import base64
import os
import random
import re
import shutil
import time
import urllib
from datetime import datetime
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont
try:
    from pySmartDL import SmartDL
except ImportError:
    SmartDL = None

from telethon.errors import FloodWaitError
from telethon.tl import functions

try:
    from urlextract import URLExtract
except ImportError:
    URLExtract = None

from userbot.core.jobs import CancellationToken, JobPriority, job_supervisor

from ..Config import Config
from ..helpers.utils import _format
from ..sql_helper.global_list import (
    add_to_list,
    get_collection_list,
    is_in_list,
    rm_from_list,
)
from ..sql_helper.globals import addgvar, delgvar, gvarstatus
from . import BOTLOG, BOTLOG_CHATID, _catutils, catub, edit_delete, logging

plugin_category = "tools"

LOGS = logging.getLogger(__name__)

FONT_FILE_TO_USE = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
autopic_path = os.path.join(os.getcwd(), "userbot", "original_pic.png")
digitalpic_path = os.path.join(os.getcwd(), "userbot", "digital_pic.png")
autophoto_path = os.path.join(os.getcwd(), "userbot", "photo_pfp.png")

COLLECTION_STRINGS = {
    "batmanpfp_strings": [
        "awesome-batman-wallpapers",
        "batman-arkham-knight-4k-wallpaper",
        "batman-hd-wallpapers-1080p",
        "the-joker-hd-wallpaper",
        "dark-knight-joker-wallpaper",
    ],
    "thorpfp_strings": [
        "thor-wallpapers",
        "thor-wallpaper",
        "thor-iphone-wallpaper",
        "thor-wallpaper-hd",
    ],
}


def fetch_data():
    global DEFAULTUSERBIO, DEFAULTUSER, CHANGE_TIME, DEFAULT_PIC, digitalpfp
    DEFAULTUSERBIO = gvarstatus("DEFAULT_BIO") or " ᗯᗩᏆᎢᏆᑎᏀ ᏞᏆᏦᗴ ᎢᏆᗰᗴ  "
    DEFAULTUSER = gvarstatus("DEFAULT_NAME") or Config.ALIVE_NAME
    try:
        CHANGE_TIME = int(gvarstatus("CHANGE_TIME") or "60")
    except (ValueError, TypeError):
        CHANGE_TIME = 60
    DEFAULT_PIC = gvarstatus("DEFAULT_PIC") or None
    digitalpfp = (
        gvarstatus("DIGITAL_PIC") or "https://graph.org/file/aeaebe33b1f3988a0b690.jpg"
    )


async def start_profile_job(job_name: str, coro_fn):
    """Start or restart a background job supervised under JobSupervisor."""
    await stop_profile_job(job_name)
    return await job_supervisor.submit(
        job_name,
        coro_fn,
        plugin_id="autoprofile",
        priority=JobPriority.BACKGROUND,
    )


async def stop_profile_job(job_name: str):
    """Cancel an active profile job by name."""
    for j in job_supervisor.list_jobs(active_only=True):
        if j.plugin_id == "autoprofile" and j.name == job_name:
            await job_supervisor.cancel_job(j.job_id)


async def autopicloop(token: Optional[CancellationToken] = None):
    fetch_data()
    AUTOPICSTART = gvarstatus("autopic") == "true"
    if AUTOPICSTART and DEFAULT_PIC is None:
        if BOTLOG:
            return await catub.send_message(
                BOTLOG_CHATID,
                "**Error**\n`For functing of autopic you need to set DEFAULT_PIC var in Database vars`",
            )
        return
    counter = 30
    if gvarstatus("autopic") is not None:
        try:
            counter = int(gvarstatus("autopic_counter"))
        except Exception as e:
            LOGS.warning(str(e))
    while AUTOPICSTART and (token is None or not token.is_cancelled):
        if not os.path.exists(autopic_path):
            downloader = SmartDL(DEFAULT_PIC, autopic_path, progress_bar=False)
            downloader.start(blocking=False)
            while not downloader.isFinished():
                if token and token.is_cancelled:
                    return
                await asyncio.sleep(0.1)
        shutil.copy(autopic_path, autophoto_path)
        im = Image.open(autophoto_path)
        file_test = im.rotate(counter, expand=False).save(autophoto_path, "PNG")
        current_time = datetime.now().strftime("  Time: %H:%M \n  Date: %d.%m.%y ")
        img = Image.open(autophoto_path)
        drawn_text = ImageDraw.Draw(img)
        fnt = ImageFont.truetype(FONT_FILE_TO_USE, 30)
        drawn_text.text((150, 250), current_time, font=fnt, fill=(124, 252, 0))
        img.save(autophoto_path)
        file = await catub.upload_file(autophoto_path)
        try:
            await catub(functions.photos.UploadProfilePhotoRequest(file))
            if os.path.exists(autophoto_path):
                os.remove(autophoto_path)
            counter += counter
            if token:
                await token.sleep(CHANGE_TIME)
            else:
                await asyncio.sleep(CHANGE_TIME)
        except asyncio.CancelledError:
            break
        except BaseException:
            return
        AUTOPICSTART = gvarstatus("autopic") == "true"


async def custompfploop(token: Optional[CancellationToken] = None):
    fetch_data()
    CUSTOMPICSTART = gvarstatus("CUSTOM_PFP") == "true"
    i = 0
    while CUSTOMPICSTART and (token is None or not token.is_cancelled):
        collection = get_collection_list("CUSTOM_PFP_LINKS")
        if len(collection) == 0:
            LOGS.error("No custom pfp images to set.")
            return
        pic = random.choice(list(collection))
        urllib.request.urlretrieve(pic, "donottouch.jpg")
        file = await catub.upload_file("donottouch.jpg")
        try:
            if i > 0:
                await catub(
                    functions.photos.DeletePhotosRequest(
                        await catub.get_profile_photos("me", limit=1)
                    )
                )
            i += 1
            await catub(functions.photos.UploadProfilePhotoRequest(file))
            if os.path.exists("donottouch.jpg"):
                os.remove("donottouch.jpg")
            if token:
                await token.sleep(CHANGE_TIME)
            else:
                await asyncio.sleep(CHANGE_TIME)
        except asyncio.CancelledError:
            break
        except BaseException:
            return
        CUSTOMPICSTART = gvarstatus("CUSTOM_PFP") == "true"


async def digitalpicloop(token: Optional[CancellationToken] = None):
    fetch_data()
    DIGITALPICSTART = gvarstatus("digitalpic") == "true"
    i = 0
    while DIGITALPICSTART and (token is None or not token.is_cancelled):
        if not os.path.exists(digitalpic_path):
            downloader = SmartDL(digitalpfp, digitalpic_path, progress_bar=False)
            downloader.start(blocking=False)
            while not downloader.isFinished():
                if token and token.is_cancelled:
                    return
                await asyncio.sleep(0.1)
        shutil.copy(digitalpic_path, autophoto_path)
        Image.open(autophoto_path)
        current_time = datetime.now().strftime("%H:%M")
        img = Image.open(autophoto_path)
        drawn_text = ImageDraw.Draw(img)
        cat = str(base64.b64decode("dXNlcmJvdC9oZWxwZXJzL3N0eWxlcy9kaWdpdGFsLnR0Zg=="))[
            2:36
        ]
        fnt = ImageFont.truetype(cat, 200)
        drawn_text.text((350, 100), current_time, font=fnt, fill=(124, 252, 0))
        img.save(autophoto_path)
        file = await catub.upload_file(autophoto_path)
        try:
            if i > 0:
                await catub(
                    functions.photos.DeletePhotosRequest(
                        await catub.get_profile_photos("me", limit=1)
                    )
                )
            i += 1
            await catub(functions.photos.UploadProfilePhotoRequest(file))
            if os.path.exists(autophoto_path):
                os.remove(autophoto_path)
            if token:
                await token.sleep(60)
            else:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except BaseException:
            return
        DIGITALPICSTART = gvarstatus("digitalpic") == "true"


async def bloom_pfploop(token: Optional[CancellationToken] = None):
    fetch_data()
    BLOOMSTART = gvarstatus("bloom") == "true"
    if BLOOMSTART and DEFAULT_PIC is None:
        if BOTLOG:
            return await catub.send_message(
                BOTLOG_CHATID,
                "**Error**\n`For functing of bloom you need to set DEFAULT_PIC var in Database vars`",
            )
        return
    while BLOOMSTART and (token is None or not token.is_cancelled):
        if not os.path.exists(autopic_path):
            downloader = SmartDL(DEFAULT_PIC, autopic_path, progress_bar=False)
            downloader.start(blocking=False)
            while not downloader.isFinished():
                if token and token.is_cancelled:
                    return
                await asyncio.sleep(0.1)
        # RIP Danger zone Here no editing here plox
        R = random.randint(0, 256)
        B = random.randint(0, 256)
        G = random.randint(0, 256)
        FR = 256 - R
        FB = 256 - B
        FG = 256 - G
        shutil.copy(autopic_path, autophoto_path)
        image = Image.open(autophoto_path)
        image.paste((R, G, B), [0, 0, image.size[0], image.size[1]])
        image.save(autophoto_path)
        current_time = datetime.now().strftime("\n Time: %H:%M:%S \n \n Date: %d/%m/%y")
        img = Image.open(autophoto_path)
        drawn_text = ImageDraw.Draw(img)
        fnt = ImageFont.truetype(FONT_FILE_TO_USE, 60)
        ofnt = ImageFont.truetype(FONT_FILE_TO_USE, 250)
        drawn_text.text((95, 250), current_time, font=fnt, fill=(FR, FG, FB))
        drawn_text.text((95, 250), "      😈", font=ofnt, fill=(FR, FG, FB))
        img.save(autophoto_path)
        file = await catub.upload_file(autophoto_path)
        try:
            await catub(functions.photos.UploadProfilePhotoRequest(file))
            if os.path.exists(autophoto_path):
                os.remove(autophoto_path)
            if token:
                await token.sleep(CHANGE_TIME)
            else:
                await asyncio.sleep(CHANGE_TIME)
        except asyncio.CancelledError:
            break
        except BaseException:
            return
        BLOOMSTART = gvarstatus("bloom") == "true"


async def autoname_loop(token: Optional[CancellationToken] = None):
    fetch_data()
    while (token is None or not token.is_cancelled) and gvarstatus("autoname") == "true":
        DM = time.strftime("%d-%m-%y")
        HM = time.strftime("%H:%M")
        name = f"⌚️ {HM}||›  {DEFAULTUSER} ‹||📅 {DM}"
        LOGS.info(name)
        try:
            await catub(functions.account.UpdateProfileRequest(first_name=name))
        except FloodWaitError as ex:
            LOGS.warning(str(ex))
            if token:
                await token.sleep(ex.seconds)
            else:
                await asyncio.sleep(ex.seconds)
        except asyncio.CancelledError:
            break
        except Exception as e:
            LOGS.warning("autoname error: %s", e)
        if token:
            await token.sleep(CHANGE_TIME)
        else:
            await asyncio.sleep(CHANGE_TIME)


async def autobio_loop(token: Optional[CancellationToken] = None):
    fetch_data()
    while (token is None or not token.is_cancelled) and gvarstatus("autobio") == "true":
        DMY = time.strftime("%d.%m.%Y")
        HM = time.strftime("%H:%M")
        bio = f"📅 {DMY} | {DEFAULTUSERBIO} | ⌚️ {HM}"
        LOGS.info(bio)
        try:
            await catub(functions.account.UpdateProfileRequest(about=bio))
        except FloodWaitError as ex:
            LOGS.warning(str(ex))
            if token:
                await token.sleep(ex.seconds)
            else:
                await asyncio.sleep(ex.seconds)
        except asyncio.CancelledError:
            break
        except Exception as e:
            LOGS.warning("autobio error: %s", e)
        if token:
            await token.sleep(CHANGE_TIME)
        else:
            await asyncio.sleep(CHANGE_TIME)


async def animeprofilepic(collection_images):
    rnd = random.randint(0, len(collection_images) - 1)
    pack = collection_images[rnd]
    pc = requests.get(f"http://getwallpapers.com/collection/{pack}").text
    f = re.compile(r"/\w+/full.+.jpg")
    f = f.findall(pc)
    fy = f"http://getwallpapers.com{random.choice(f)}"
    if not os.path.exists("f.ttf"):
        urllib.request.urlretrieve(
            "https://github.com/rebel6969/mym/raw/master/Rebel-robot-Regular.ttf",
            "f.ttf",
        )
    img = requests.get(fy)
    with open("donottouch.jpg", "wb") as outfile:
        outfile.write(img.content)
    return "donottouch.jpg"


async def autopfp_start(token: Optional[CancellationToken] = None):
    fetch_data()
    if gvarstatus("autopfp_strings") is not None:
        AUTOPFP_START = True
        string_list = COLLECTION_STRINGS.get(gvarstatus("autopfp_strings"), [])
    else:
        AUTOPFP_START = False
        string_list = []
    i = 0
    while AUTOPFP_START and (token is None or not token.is_cancelled):
        if not string_list:
            break
        await animeprofilepic(string_list)
        file = await catub.upload_file("donottouch.jpg")
        if i > 0:
            await catub(
                functions.photos.DeletePhotosRequest(
                    await catub.get_profile_photos("me", limit=1)
                )
            )
        i += 1
        await catub(functions.photos.UploadProfilePhotoRequest(file))
        if os.path.exists("donottouch.jpg"):
            await _catutils.runcmd("rm -rf donottouch.jpg")
        if token:
            await token.sleep(CHANGE_TIME)
        else:
            await asyncio.sleep(CHANGE_TIME)
        AUTOPFP_START = gvarstatus("autopfp_strings") is not None


@catub.cat_cmd(
    pattern="batmanpfp$",
    command=("batmanpfp", plugin_category),
    info={
        "header": "Changes profile pic with random batman pics every 1 minute",
        "description": "Changes your profile pic every 1 minute with random batman pics.\
        If you like to change the time then set CHANGE_TIME var in Database with time (in seconds) between each change of profilepic.",
        "note": "To stop this do '.end batmanpfp'",
        "usage": "{tr}batmanpfp",
    },
)
async def _(event):
    "To set random batman profile pics"
    if gvarstatus("autopfp_strings") is not None:
        pfp_string = gvarstatus("autopfp_strings")[:-8]
        return await edit_delete(event, f"`{pfp_string} is already running.`")
    addgvar("autopfp_strings", "batmanpfp_strings")
    await edit_delete(event, "`Starting batman Profile Pic.`")
    await start_profile_job("autoprofile_pfp", autopfp_start)


@catub.cat_cmd(
    pattern="thorpfp$",
    command=("thorpfp", plugin_category),
    info={
        "header": "Changes profile pic with random thor pics every 1 minute",
        "description": "Changes your profile pic every 1 minute with random thor pics.\
        If you like to change the time then set CHANGE_TIME var in Database with time(in seconds) between each change of profilepic.",
        "note": "To stop this do '.end thorpfp'",
        "usage": "{tr}thorpfp",
    },
)
async def _(event):
    "To set random thor profile pics"
    if gvarstatus("autopfp_strings") is not None:
        pfp_string = gvarstatus("autopfp_strings")[:-8]
        return await edit_delete(event, f"`{pfp_string} is already running.`")
    addgvar("autopfp_strings", "thorpfp_strings")
    await edit_delete(event, "`Starting thor Profile Pic.`")
    await start_profile_job("autoprofile_pfp", autopfp_start)


@catub.cat_cmd(
    pattern=r"autopic ?([\s\S]*)",
    command=("autopic", plugin_category),
    info={
        "header": "Changes profile pic every 1 minute with the custom pic with time",
        "description": "If you like to change the time interval for every new pic change \
            then set CHANGE_TIME var in Database with time(in seconds) between each change of profilepic.",
        "options": "you can give integer input with cmd like 40,55,75 ..etc.\
             So that your profile pic will rotate with that specific angle",
        "note": "For functioning of this cmd you need to set DEFAULT_PIC var in Database. \
            To stop this do '.end autopic'",
        "usage": [
            "{tr}autopic",
            "{tr}autopic <any integer>",
        ],
    },
)
async def _(event):
    "To set time on your profile pic"
    fetch_data()
    if DEFAULT_PIC is None:
        return await edit_delete(
            event,
            "**Error**\nFor functing of autopic you need to set DEFAULT_PIC var in Database vars",
            parse_mode=_format.parse_pre,
        )
    downloader = SmartDL(DEFAULT_PIC, autopic_path, progress_bar=False)
    downloader.start(blocking=False)
    while not downloader.isFinished():
        pass
    input_str = event.pattern_match.group(1)
    if input_str:
        try:
            input_str = int(input_str)
        except ValueError:
            input_str = 60
    elif gvarstatus("autopic_counter") is None:
        addgvar("autopic_counter", 30)
    if gvarstatus("autopic") is not None and gvarstatus("autopic") == "true":
        return await edit_delete(event, "`Autopic is already enabled`")
    addgvar("autopic", True)
    if input_str:
        addgvar("autopic_counter", input_str)
    await edit_delete(event, "`Autopic has been started by my Master`")
    await start_profile_job("autoprofile_autopic", autopicloop)


@catub.cat_cmd(
    pattern="digitalpfp$",
    command=("digitalpfp", plugin_category),
    info={
        "header": "Updates your profile pic every 1 minute with time on it",
        "description": "Deletes old profile pic and Update profile pic with new image with time on it.\
             You can change this image by setting DIGITAL_PIC var in Database with telegraph image link",
        "note": "To stop this do '.end digitalpfp'",
        "usage": "{tr}digitalpfp",
    },
)
async def _(event):
    "To set random colour pic with time to profile pic"
    downloader = SmartDL(digitalpfp, digitalpic_path, progress_bar=False)
    downloader.start(blocking=False)
    while not downloader.isFinished():
        pass
    if gvarstatus("digitalpic") is not None and gvarstatus("digitalpic") == "true":
        return await edit_delete(event, "`Digitalpic is already enabled`")
    addgvar("digitalpic", True)
    await edit_delete(event, "`digitalpfp has been started by my Master`")
    await start_profile_job("autoprofile_digitalpic", digitalpicloop)


@catub.cat_cmd(
    pattern="bloom$",
    command=("bloom", plugin_category),
    info={
        "header": "Changes profile pic every 1 minute with the random colour pic with time on it",
        "description": "If you like to change the time interval for every new pic chnage \
            then set CHANGE_TIME var in Database with time(in seconds) between each change of profilepic.",
        "note": "For functioning of this cmd you need to set DEFAULT_PIC var in Database. \
            To stop this do '.end bloom'",
        "usage": "{tr}bloom",
    },
)
async def _(event):
    "To set random colour pic with time to profile pic"
    fetch_data()
    if DEFAULT_PIC is None:
        return await edit_delete(
            event,
            "**Error**\nFor functing of bloom you need to set DEFAULT_PIC var in Database vars",
            parse_mode=_format.parse_pre,
        )
    downloader = SmartDL(DEFAULT_PIC, autopic_path, progress_bar=True)
    downloader.start(blocking=False)
    while not downloader.isFinished():
        pass
    if gvarstatus("bloom") is not None and gvarstatus("bloom") == "true":
        return await edit_delete(event, "`Bloom is already enabled`")
    addgvar("bloom", True)
    await edit_delete(event, "`Bloom has been started by my Master`")
    await start_profile_job("autoprofile_bloom", bloom_pfploop)


@catub.cat_cmd(
    pattern=r"c(ustom)?pfp(?: |$)([\s\S]*)",
    command=("custompfp", plugin_category),
    info={
        "header": "Set Your Custom pfps",
        "description": "Set links of pic to use them as auto profile. You can use cpfp or custompfp as command",
        "flags": {
            "a": "To add links for custom pfp",
            "r": "To remove links for custom pfp",
            "l": "To get links of custom pfp",
            "s": "To stop custom pfp",
        },
        "usage": [
            "{tr}cpfp - to start",
            "{tr}cpfp <flags> <links(optional)>",
        ],
    },
)
async def useless(event):  # sourcery no-metrics
    """Custom profile pics"""
    input_str = event.pattern_match.group(2)
    ext = re.findall(r"-\w+", input_str)
    try:
        flag = ext[0].replace("-", "")
        input_str = input_str.replace(ext[0], "").strip()
    except IndexError:
        flag = None
    list_link = get_collection_list("CUSTOM_PFP_LINKS")
    if flag is None:
        if gvarstatus("CUSTOM_PFP") is not None and gvarstatus("CUSTOM_PFP") == "true":
            return await edit_delete(event, "`Custom pfp is already enabled`")
        if not list_link:
            return await edit_delete(event, "**ಠ∀ಠ  There no links for custom pfp...**")
        addgvar("CUSTOM_PFP", True)
        await edit_delete(event, "`Starting custom pfp....`")
        await start_profile_job("autoprofile_custompfp", custompfploop)
        return
    if flag == "l":
        if not list_link:
            return await edit_delete(
                event, "**ಠ∀ಠ  There no links set for custom pfp...**"
            )
        links = "**Available links for custom pfp are here:-**\n\n"
        for i, each in enumerate(list_link, start=1):
            links += f"**{i}.**  {each}\n"
        await edit_delete(event, links, 60)
        return
    if flag == "s":
        if gvarstatus("CUSTOM_PFP") is not None and gvarstatus("CUSTOM_PFP") == "true":
            delgvar("CUSTOM_PFP")
            await stop_profile_job("autoprofile_custompfp")
            await event.client(
                functions.photos.DeletePhotosRequest(
                    await event.client.get_profile_photos("me", limit=1)
                )
            )
            return await edit_delete(event, "`Custompfp has been stopped now`")
        return await edit_delete(event, "`Custompfp haven't enabled`")
    reply = await event.get_reply_message()
    if not input_str and reply:
        input_str = reply.text
    if not input_str:
        return await edit_delete(
            event, "**ಠ∀ಠ  Reply to valid link or give valid link url as input...**"
        )
    extractor = URLExtract()
    plink = extractor.find_urls(input_str)
    if len(plink) == 0:
        return await edit_delete(
            event, "**ಠ∀ಠ  Reply to valid link or give valid link url as input...**"
        )
    if flag == "a":
        for i in plink:
            if not is_in_list("CUSTOM_PFP_LINKS", i):
                add_to_list("CUSTOM_PFP_LINKS", i)
        await edit_delete(
            event, f"**{len(plink)} pictures sucessfully added to custom pfps**"
        )
    elif flag == "r":
        for i in plink:
            if is_in_list("CUSTOM_PFP_LINKS", i):
                rm_from_list("CUSTOM_PFP_LINKS", i)
        await edit_delete(
            event, f"**{len(plink)} pictures sucessfully removed from custom pfps**"
        )


@catub.cat_cmd(
    pattern="autoname$",
    command=("autoname", plugin_category),
    info={
        "header": "Changes your name with time",
        "description": "Updates your profile name along with time. Set DEFAULT_USER var in Database.",
        "note": "To stop this do '.end autoname'",
        "usage": "{tr}autoname",
    },
)
async def _(event):
    "To set your display name along with time"
    if gvarstatus("autoname") is not None and gvarstatus("autoname") == "true":
        return await edit_delete(event, "`Autoname is already enabled`")
    addgvar("autoname", True)
    await edit_delete(event, "`AutoName has been started by my Master `")
    await start_profile_job("autoprofile_autoname", autoname_loop)


@catub.cat_cmd(
    pattern="autobio$",
    command=("autobio", plugin_category),
    info={
        "header": "Changes your bio with time",
        "description": "Updates your profile bio along with time. Set DEFAULT_BIO var in Database with your fav bio,",
        "note": "To stop this do '.end autobio'",
        "usage": "{tr}autobio",
    },
)
async def _(event):
    "To update your bio along with time"
    if gvarstatus("autobio") is not None and gvarstatus("autobio") == "true":
        return await edit_delete(event, "`Autobio is already enabled`")
    addgvar("autobio", True)
    await edit_delete(event, "`Autobio has been started by my Master `")
    await start_profile_job("autoprofile_autobio", autobio_loop)


@catub.cat_cmd(
    pattern=r"end ([\s\S]*)",
    command=("end", plugin_category),
    info={
        "header": "To stop the functions of autoprofile",
        "description": "If you want to stop autoprofile functions then use this cmd.",
        "options": {
            "autopic": "To stop autopic",
            "digitalpfp": "To stop difitalpfp",
            "bloom": "To stop bloom",
            "autoname": "To stop autoname",
            "autobio": "To stop autobio",
            "thorpfp": "To stop thorpfp",
            "batmanpfp": "To stop batmanpfp",
            "spam": "To stop spam",
        },
        "usage": "{tr}end <option>",
        "examples": ["{tr}end autopic"],
    },
)
async def _(event):  # sourcery no-metrics  # sourcery skip: low-code-quality
    "To stop the functions of autoprofile plugin"
    fetch_data()
    input_str = event.pattern_match.group(1)
    if input_str == "thorpfp" and gvarstatus("autopfp_strings") is not None:
        pfp_string = gvarstatus("autopfp_strings")[:-8]
        if pfp_string != "thorpfp":
            return await edit_delete(event, "`thorpfp is not started`")
        await stop_profile_job("autoprofile_pfp")
        await event.client(
            functions.photos.DeletePhotosRequest(
                await event.client.get_profile_photos("me", limit=1)
            )
        )
        delgvar("autopfp_strings")
        return await edit_delete(event, "`thorpfp has been stopped now`")
    if input_str == "batmanpfp" and gvarstatus("autopfp_strings") is not None:
        pfp_string = gvarstatus("autopfp_strings")[:-8]
        if pfp_string != "batmanpfp":
            return await edit_delete(event, "`batmanpfp is not started`")
        await stop_profile_job("autoprofile_pfp")
        await event.client(
            functions.photos.DeletePhotosRequest(
                await event.client.get_profile_photos("me", limit=1)
            )
        )
        delgvar("autopfp_strings")
        return await edit_delete(event, "`batmanpfp has been stopped now`")
    if input_str == "autopic":
        if gvarstatus("autopic") is not None and gvarstatus("autopic") == "true":
            delgvar("autopic")
            await stop_profile_job("autoprofile_autopic")
            if os.path.exists(autopic_path):
                file = await event.client.upload_file(autopic_path)
                try:
                    await event.client(functions.photos.UploadProfilePhotoRequest(file))
                    os.remove(autopic_path)
                except BaseException:
                    return
            return await edit_delete(event, "`Autopic has been stopped now`")
        return await edit_delete(event, "`Autopic haven't enabled`")
    if input_str == "digitalpfp":
        if gvarstatus("digitalpic") is not None and gvarstatus("digitalpic") == "true":
            delgvar("digitalpic")
            await stop_profile_job("autoprofile_digitalpic")
            await event.client(
                functions.photos.DeletePhotosRequest(
                    await event.client.get_profile_photos("me", limit=1)
                )
            )
            return await edit_delete(event, "`Digitalpfp has been stopped now`")
        return await edit_delete(event, "`Digitalpfp haven't enabled`")
    if input_str == "bloom":
        if gvarstatus("bloom") is not None and gvarstatus("bloom") == "true":
            delgvar("bloom")
            await stop_profile_job("autoprofile_bloom")
            if os.path.exists(autopic_path):
                file = await event.client.upload_file(autopic_path)
                try:
                    await event.client(functions.photos.UploadProfilePhotoRequest(file))
                    os.remove(autopic_path)
                except BaseException:
                    return
            return await edit_delete(event, "`Bloom has been stopped now`")
        return await edit_delete(event, "`Bloom haven't enabled`")
    if input_str == "autoname":
        if gvarstatus("autoname") is not None and gvarstatus("autoname") == "true":
            delgvar("autoname")
            await stop_profile_job("autoprofile_autoname")
            await event.client(
                functions.account.UpdateProfileRequest(first_name=DEFAULTUSER)
            )
            return await edit_delete(event, "`Autoname has been stopped now`")
        return await edit_delete(event, "`Autoname haven't enabled`")
    if input_str == "autobio":
        if gvarstatus("autobio") is not None and gvarstatus("autobio") == "true":
            delgvar("autobio")
            await stop_profile_job("autoprofile_autobio")
            await event.client(
                functions.account.UpdateProfileRequest(about=DEFAULTUSERBIO)
            )
            return await edit_delete(event, "`Autobio has been stopped now`")
        return await edit_delete(event, "`Autobio haven't enabled`")
    if input_str == "spam":
        if gvarstatus("spamwork") is not None and gvarstatus("spamwork") == "true":
            delgvar("spamwork")
            return await edit_delete(event, "`Spam cmd has been stopped now`")
        return await edit_delete(event, "`You haven't started spam`")
    if input_str == "all":
        await job_supervisor.cancel_plugin_jobs("autoprofile")
        delgvar("autopfp_strings")
        delgvar("autopic")
        delgvar("digitalpic")
        delgvar("bloom")
        delgvar("autoname")
        delgvar("autobio")
        delgvar("CUSTOM_PFP")
        return await edit_delete(event, "`All autoprofile background jobs stopped and cleared.`")
    END_CMDS = [
        "autopic",
        "digitalpfp",
        "bloom",
        "autoname",
        "autobio",
        "thorpfp",
        "batmanpfp",
        "spam",
        "all",
    ]
    if input_str not in END_CMDS:
        await edit_delete(
            event,
            f"{input_str} is invalid end command.Mention clearly what should i end.",
            parse_mode=_format.parse_pre,
        )


async def on_load(ctx=None):
    """Resume any enabled autoprofile background jobs under JobSupervisor."""
    fetch_data()
    if gvarstatus("autopfp_strings") is not None:
        await start_profile_job("autoprofile_pfp", autopfp_start)
    if gvarstatus("autopic") == "true":
        await start_profile_job("autoprofile_autopic", autopicloop)
    if gvarstatus("digitalpic") == "true":
        await start_profile_job("autoprofile_digitalpic", digitalpicloop)
    if gvarstatus("bloom") == "true":
        await start_profile_job("autoprofile_bloom", bloom_pfploop)
    if gvarstatus("autoname") == "true":
        await start_profile_job("autoprofile_autoname", autoname_loop)
    if gvarstatus("autobio") == "true":
        await start_profile_job("autoprofile_autobio", autobio_loop)
    if gvarstatus("CUSTOM_PFP") == "true":
        await start_profile_job("autoprofile_custompfp", custompfploop)


async def on_unload(ctx=None):
    """Cancel all active autoprofile jobs."""
    await job_supervisor.cancel_plugin_jobs("autoprofile")
