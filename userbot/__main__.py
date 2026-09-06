# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris UserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import os
import signal
import sys

import userbot
from userbot import BOTLOG_CHATID, PM_LOGGER_GROUP_ID

from telethon import events

from userbot.core.callbacks import secure_callbacks
from userbot.core.jobs.supervisor import job_supervisor
from userbot.core.web import dashboard
from userbot.core.health import HealthServer
from userbot.core.tasks import task_manager

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


cmdhr = Config.COMMAND_HAND_LER


def require_core_plugins(report, required=("alive", "ping")):
    missing = sorted(set(required) - set(report.loaded))
    if missing:
        raise RuntimeError(
            "Essential command plugins failed to load: " + ", ".join(missing)
        )


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
    command_report = await load_plugins("plugins")
    assistant_report = await load_plugins("assistant")
    require_core_plugins(command_report)
    LOGS.info("============================================================================")
    LOGS.info("||             ◈ A E T H E R I S  U S E R B O T  v5.0 ◈                   ||")
    LOGS.info(
        "||       Core ready: %d command plugins, %d assistant plugins loaded       ||",
        command_report.success, assistant_report.success,
    )
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


async def main():
    ready = False
    health = HealthServer(
        lambda: ready and catub.is_connected() and catub.tgbot.is_connected(),
        port=int(os.environ.get("PORT", "8080")),
    )
    try:
        await health.start()
        LOGS.info("Starting Aetheris Userbot Engine...")
        await setup_bot()
        await startup_process()
        await externalrepo()
        ready = True
        if len(sys.argv) in {1, 3, 4}:
            await catub.run_until_disconnected()
    finally:
        ready = False
        # A failure in one cleanup must not skip the other owned services.
        for name, close in (
            ("health", health.stop),
            ("dashboard", dashboard.stop),
            ("jobs", job_supervisor.stop),
            ("legacy tasks", task_manager.stop),
            ("assistant", catub.tgbot.disconnect),
            ("user client", catub.disconnect),
        ):
            try:
                await close()
            except Exception:
                LOGS.exception("Could not close %s", name)
        from userbot import sql_helper
        try:
            sql_helper.SESSION.remove()
        finally:
            if sql_helper.ENGINE is not None:
                sql_helper.ENGINE.dispose()


def run():
    loop = catub.loop
    task = loop.create_task(main())
    requested = False

    def request_stop(*_):
        nonlocal requested
        if not requested:
            requested = True
            loop.call_soon_threadsafe(task.cancel)

    previous = {sig: signal.signal(sig, request_stop)
                for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        loop.run_until_complete(task)
    except asyncio.CancelledError:
        if not requested:
            raise
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    run()
