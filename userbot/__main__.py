# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris UserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import contextlib
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import userbot
from userbot import BOTLOG_CHATID, PM_LOGGER_GROUP_ID

from telethon import events

from userbot.core.callbacks import secure_callbacks
from userbot.core.jobs.supervisor import job_supervisor
from userbot.core.web import dashboard

from .Config import Config
from .core.logger import logging
from .core.session import catub
from .utils import (
    add_bot_to_logger_group,
    install_externalrepo,
    load_plugins,
    setup_bot,
    startupmessage,
    verifyLoggerGroup,
)

LOGS = logging.getLogger("Aetheris")

LOGS.info(userbot.__copyright__)
LOGS.info(f"Licensed under the terms of the {userbot.__license__}")


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Aetheris Userbot is online and healthy!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def start_health_server():
    try:
        raw_port = os.environ.get("PORT", "8080")
        try:
            port = int(str(raw_port).strip())
        except (ValueError, TypeError):
            port = 8080
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        LOGS.info(f"Aetheris health check daemon active on port {port}")
        server.serve_forever()
    except Exception as e:
        LOGS.warning(f"Could not start background health server: {e}")


threading.Thread(target=start_health_server, daemon=True).start()

cmdhr = Config.COMMAND_HAND_LER

try:
    LOGS.info("Starting Aetheris Userbot Engine...")
    catub.loop.run_until_complete(setup_bot())
    LOGS.info("Aetheris Bot Startup Completed")
except Exception as e:
    LOGS.error(f"Startup Failure: {e}")
    sys.exit()


async def startup_process():
    await job_supervisor.start()
    try:
        if hasattr(catub, "tgbot") and catub.tgbot:
            catub.tgbot.add_event_handler(secure_callbacks.handle_callback_query, events.CallbackQuery)
        catub.add_event_handler(secure_callbacks.handle_callback_query, events.CallbackQuery)
    except Exception as cb_err:
        LOGS.warning(f"Could not bind callback query handler: {cb_err}")

    try:
        await dashboard.start()
    except Exception as dash_err:
        LOGS.warning(f"Dashboard startup skipped: {dash_err}")

    await verifyLoggerGroup()
    await load_plugins("plugins")
    await load_plugins("assistant")
    LOGS.info("============================================================================")
    LOGS.info("||             ◈ A E T H E R I S  U S E R B O T  v5.0 ◈                   ||")
    LOGS.info("||               MTProto Automation Core Online & Operational             ||")
    LOGS.info(f"||         Type {cmdhr}alive or {cmdhr}ping to verify your live instance        ||")
    LOGS.info("============================================================================")
    await verifyLoggerGroup()
    await add_bot_to_logger_group(BOTLOG_CHATID)
    if PM_LOGGER_GROUP_ID != -100:
        await add_bot_to_logger_group(PM_LOGGER_GROUP_ID)
    await startupmessage()
    return


async def externalrepo():
    string = "<b>Your external repo plugins have imported.</b>\n\n"
    if Config.EXTERNAL_REPO:
        data = await install_externalrepo(
            Config.EXTERNAL_REPO, Config.EXTERNAL_REPOBRANCH, "xtraplugins"
        )
        string += f"<b>➜ Repo:  </b><a href='{data[0]}'><b>{data[1]}</b></a>\n<b>     • Imported Plugins:</b>  <code>{data[2]}</code>\n<b>     • Failed to Import:</b>  <code>{', '.join(data[3])}</code>\n\n"
    if Config.BADCAT:
        data = await install_externalrepo(
            Config.BADCAT_REPO, Config.BADCAT_REPOBRANCH, "badcatext"
        )
        string += f"<b>➜ Repo:  </b><a href='{data[0]}'><b>{data[1]}</b></a>\n<b>     • Imported Plugins:</b>  <code>{data[2]}</code>\n<b>     • Failed to Import:</b>  <code>{', '.join(data[3])}</code>\n\n"
    if Config.VCMODE:
        data = await install_externalrepo(Config.VC_REPO, Config.VC_REPOBRANCH, "catvc")
        string += f"<b>➜ Repo:  </b><a href='{data[0]}'><b>{data[1]}</b></a>\n<b>     • Imported Plugins:</b>  <code>{data[2]}</code>\n<b>     • Failed to Import:</b>  <code>{', '.join(data[3])}</code>\n\n"
    if "Imported Plugins" in string:
        await catub.tgbot.send_message(BOTLOG_CHATID, string, parse_mode="html")


catub.loop.run_until_complete(startup_process())
catub.loop.run_until_complete(externalrepo())

if len(sys.argv) in {1, 3, 4}:
    with contextlib.suppress(ConnectionError):
        catub.run_until_disconnected()
else:
    catub.disconnect()
