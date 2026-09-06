# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.

# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement".

# Please see: https://github.com/TgCatUB/catuserbot/blob/master/LICENSE
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import glob
import os
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from telethon import Button, functions, types, utils

from userbot import BOTLOG, BOTLOG_CHATID, PM_LOGGER_GROUP_ID, catversion

from ..Config import Config
from ..core.logger import logging
from ..core.session import catub
from ..helpers.utils import install_pip
from ..helpers.utils.utils import runcmd
from ..sql_helper.global_collection import (
    del_keyword_collectionlist,
    get_item_collectionlist,
)
from ..sql_helper.globals import addgvar, gvarstatus
from .pluginmanager import load_module
from .tools import create_supergroup

ENV = bool(os.environ.get("ENV", False))
LOGS = logging.getLogger("CatUBStartUP")
cmdhr = Config.COMMAND_HAND_LER

VPS_NOLOAD = []
if ENV:
    VPS_NOLOAD = ["vps"]
elif os.path.exists("config.py"):
    VPS_NOLOAD = ["heroku"]


@dataclass
class PluginLoadReport:
    """One startup generation's real import outcome."""

    folder: str
    loaded: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)

    @property
    def success(self):
        return len(self.loaded)

    # Preserve the external-repository helper's historical tuple unpacking.
    def __iter__(self):
        yield self.success
        yield list(self.failed) or ["None"]


async def setup_bot():
    """
    To set up bot for userbot
    """
    try:
        await catub.connect()
        config = await catub(functions.help.GetConfigRequest())
        for option in config.dc_options:
            if option.ip_address == catub.session.server_address:
                if catub.session.dc_id != option.id:
                    LOGS.warning(
                        f"Fixed DC ID in session from {catub.session.dc_id}"
                        f" to {option.id}"
                    )
                catub.session.set_dc(option.id, option.ip_address, option.port)
                catub.session.save()
                break
        if Config.TG_BOT_TOKEN:
            await catub.tgbot.start(bot_token=Config.TG_BOT_TOKEN)
        else:
            await catub.tgbot.connect()
        bot_details = await catub.tgbot.get_me()
        if bot_details:
            Config.TG_BOT_USERNAME = f"@{bot_details.username}"
        catub.me = await catub.get_me()
        if not catub.me:
            LOGS.critical(
                "CRITICAL: Failed to authenticate user account! STRING_SESSION is missing, invalid, or expired. "
                "Please run 'python stringsetup.py' to generate your session string and set STRING_SESSION."
            )
            sys.exit(1)
        if Config.OWNER_ID and Config.OWNER_ID != utils.get_peer_id(catub.me):
            raise RuntimeError("Connected Telegram account does not match OWNER_ID")
        catub.uid = catub.tgbot.uid = utils.get_peer_id(catub.me)
        if Config.OWNER_ID == 0:
            Config.OWNER_ID = utils.get_peer_id(catub.me)
    except Exception as e:
        LOGS.critical(
            f"Telegram Authentication Failure: {e}. "
            "Please check that APP_ID, API_HASH, and STRING_SESSION are valid credentials, not placeholder values!"
        )
        sys.exit(1)


async def startupmessage():
    """
    Start up message in telegram logger group
    """
    try:
        if BOTLOG:
            pic = (
                gvarstatus("STARTUP_PIC")
                or gvarstatus("ALIVE_PIC")
                or getattr(Config, "STARTUP_PIC", None)
                or "https://graph.org/file/4e3ba8e8f7e535d5a2abe.jpg"
            )
            caption = (
                f"◈ ─── **A E T H E R I S  U S E R B O T** ─── ◈\n\n"
                f"⚡ **Status  :** `Online & Operational`\n"
                f"⏳ **Version :** `v{catversion}`\n"
                f"◈ ──────────────────────────── ◈"
            )
            Config.AETHERISLOGO = Config.CATUBLOGO = await catub.tgbot.send_file(
                BOTLOG_CHATID,
                pic,
                caption=caption,
            )
    except Exception as e:
        LOGS.error(e)
        return None
    try:
        msg_details = list(get_item_collectionlist("restart_update"))
        if msg_details:
            msg_details = msg_details[0]
    except Exception as e:
        LOGS.error(e)
        return None
    try:
        if msg_details:
            await catub.check_testcases()
            message = await catub.get_messages(msg_details[0], ids=msg_details[1])
            text = message.text + "\n\n**Ok Bot is Back and Alive.**"
            await catub.edit_message(msg_details[0], msg_details[1], text)
            if gvarstatus("restartupdate") is not None:
                await catub.send_message(
                    msg_details[0],
                    f"{cmdhr}ping",
                    reply_to=msg_details[1],
                    schedule=timedelta(seconds=10),
                )
            del_keyword_collectionlist("restart_update")
    except Exception as e:
        LOGS.error(e)
        return None


async def add_bot_to_logger_group(chat_id):
    """
    To add bot to logger groups
    """
    bot_details = await catub.tgbot.get_me()
    try:
        await catub(
            functions.messages.AddChatUserRequest(
                chat_id=chat_id,
                user_id=bot_details.username,
                fwd_limit=1000000,
            )
        )
    except BaseException:
        try:
            await catub(
                functions.channels.InviteToChannelRequest(
                    channel=chat_id,
                    users=[bot_details.username],
                )
            )
        except Exception as e:
            LOGS.error(str(e))


async def load_plugins(folder, extfolder=None):
    """
    To load plugins from the mentioned folder
    """
    if extfolder:
        path = f"{extfolder}/*.py"
        plugin_path = extfolder
    else:
        path = f"userbot/{folder}/*.py"
        plugin_path = f"userbot/{folder}"
    files = glob.glob(path)
    files.sort()
    report = PluginLoadReport(folder=plugin_path)
    for name in files:
        with open(name) as f:
            path1 = Path(f.name)
            shortname = path1.stem
            pluginname = shortname.replace(".py", "")
            if pluginname == "__init__":
                continue
            try:
                if (pluginname not in Config.NO_LOAD) and (
                    pluginname not in VPS_NOLOAD
                ):
                    flag = True
                    check = 0
                    while flag:
                        try:
                            load_module(
                                pluginname,
                                plugin_path=plugin_path,
                            )
                            report.failed.pop(shortname, None)
                            report.loaded.append(shortname)
                            break
                        except ModuleNotFoundError as e:
                            install_pip(e.name)
                            check += 1
                            report.failed[shortname] = f"missing dependency: {e.name}"
                            if check > 5:
                                break
                else:
                    report.skipped.append(shortname)
                    LOGS.info("Skipping disabled plugin %s", shortname)
            except Exception as e:
                report.failed[shortname] = f"{type(e).__name__}: {e}"
                LOGS.error(
                    "Unable to load %s from %s: %s: %s",
                    shortname, plugin_path, type(e).__name__, e,
                )
    LOGS.info(
        "Plugin load summary for %s: loaded=%d failed=%d skipped=%d",
        plugin_path, report.success, len(report.failed), len(report.skipped),
    )
    if report.failed:
        LOGS.warning("Failed plugins in %s: %s", plugin_path, ", ".join(report.failed))
    return report


async def verifyLoggerGroup():
    """
    Will verify the both loggers group
    """
    flag = False
    if BOTLOG:
        try:
            entity = await catub.get_entity(BOTLOG_CHATID)
            if not isinstance(entity, types.User) and not entity.creator:
                if (
                    entity.default_banned_rights
                    and entity.default_banned_rights.send_messages
                ) or not entity.admin_rights.post_messages:
                    LOGS.info(
                        "Permissions missing to send messages for the specified PRIVATE_GROUP_BOT_API_ID."
                    )
                if (
                    entity.default_banned_rights
                    and entity.default_banned_rights.invite_users
                ) or not entity.admin_rights.invite_users:
                    LOGS.info(
                        "Permissions missing to addusers for the specified PRIVATE_GROUP_BOT_API_ID."
                    )
        except ValueError:
            LOGS.error(
                "PRIVATE_GROUP_BOT_API_ID cannot be found. Make sure it's correct."
            )
        except TypeError:
            LOGS.error(
                "PRIVATE_GROUP_BOT_API_ID is unsupported. Make sure it's correct."
            )
        except Exception as e:
            LOGS.error(
                "An Exception occured upon trying to verify the PRIVATE_GROUP_BOT_API_ID.\n"
                + str(e)
            )
    else:
        descript = "Aetheris Userbot Logging Channel. Logs events, errors, tags, and system diagnostics."
        status, groupid = await create_supergroup(
            "Aetheris Bot Log", catub, Config.TG_BOT_USERNAME, descript
        )
        if status != "error" and isinstance(groupid, int):
            addgvar("PRIVATE_GROUP_BOT_API_ID", groupid)
            LOGS.info(
                "Private Group for PRIVATE_GROUP_BOT_API_ID (Aetheris Bot Log) created successfully."
            )
            flag = True
        else:
            LOGS.error(f"Failed to auto-create logger group: {groupid}")
    if PM_LOGGER_GROUP_ID != -100:
        try:
            entity = await catub.get_entity(PM_LOGGER_GROUP_ID)
            if not isinstance(entity, types.User) and not entity.creator:
                if (
                    entity.default_banned_rights
                    and entity.default_banned_rights.send_messages
                ) or not entity.admin_rights.post_messages:
                    LOGS.info(
                        "Permissions missing to send messages for the specified PM_LOGGER_GROUP_ID."
                    )
                if (
                    entity.default_banned_rights
                    and entity.default_banned_rights.invite_users
                ) or not entity.admin_rights.invite_users:
                    LOGS.info(
                        "Permissions missing to addusers for the specified PM_LOGGER_GROUP_ID."
                    )
        except ValueError:
            LOGS.error("PM_LOGGER_GROUP_ID cannot be found. Make sure it's correct.")
        except TypeError:
            LOGS.error("PM_LOGGER_GROUP_ID is unsupported. Make sure it's correct.")
        except Exception as e:
            LOGS.error(
                "An Exception occured upon trying to verify the PM_LOGGER_GROUP_ID.\n"
                + str(e)
            )
    if flag:
        executable = sys.executable.replace(" ", "\\ ")
        args = [executable, "-m", "userbot"]
        os.execle(executable, *args, os.environ)
        sys.exit(0)


async def install_externalrepo(repo, branch, cfolder):
    CATREPO = repo
    rpath = os.path.join(cfolder, "requirements.txt")
    if CATBRANCH := branch:
        repourl = os.path.join(CATREPO, f"tree/{CATBRANCH}")
        gcmd = f"git clone -b {CATBRANCH} {CATREPO} {cfolder}"
        errtext = f"There is no branch with name `{CATBRANCH}` in your external repo {CATREPO}. Recheck branch name and correct it in vars(`EXTERNAL_REPO_BRANCH`)"
    else:
        repourl = CATREPO
        gcmd = f"git clone {CATREPO} {cfolder}"
        errtext = f"The link({CATREPO}) you provided for `EXTERNAL_REPO` in vars is invalid. please recheck that link"
    response = urllib.request.urlopen(repourl)
    if response.code != 200:
        LOGS.error(errtext)
        return await catub.tgbot.send_message(BOTLOG_CHATID, errtext)
    await runcmd(gcmd)
    if not os.path.exists(cfolder):
        LOGS.error(
            "There was a problem in cloning the external repo. please recheck external repo link"
        )
        return await catub.tgbot.send_message(
            BOTLOG_CHATID,
            "There was a problem in cloning the external repo. please recheck external repo link",
        )
    if os.path.exists(rpath):
        await runcmd(f"pip3 install --no-cache-dir -r {rpath}")
    success, failure = await load_plugins(folder="userbot", extfolder=cfolder)
    return repourl, cfolder, success, failure
