# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.

# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement".

# Please see: https://github.com/TgCatUB/catuserbot/blob/master/LICENSE
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import importlib
import sys
from pathlib import Path

from userbot import CMD_HELP, LOAD_PLUG

from ..Config import Config
from ..core import BOT_INFO, CMD_INFO, GRP_INFO, LOADED_CMDS, PLG_INFO
from ..core.plugins.legacy_reload import RegistrationTransaction
from ..core.plugins.registry import atomic_registry
from ..core.logger import logging
from ..core.managers import edit_delete, edit_or_reply
from ..core.session import catub
from ..helpers.utils import _catutils, _format, install_pip, reply_id
from .decorators import admin_cmd, sudo_cmd

LOGS = logging.getLogger("CatUserbot")


def load_module(shortname, plugin_path=None):
    """Replace registrations only if the trusted module imports successfully."""
    if not shortname.isidentifier():
        raise ValueError("Plugin name must be a Python identifier")
    module_key = f"userbot.plugins.{shortname}"
    previous = sys.modules.get(module_key)
    with RegistrationTransaction(
        [catub, getattr(catub, "tgbot", None)],
        [LOADED_CMDS, PLG_INFO, CMD_INFO, GRP_INFO, CMD_HELP, LOAD_PLUG,
         atomic_registry._handlers, atomic_registry._command_map],
        [BOT_INFO],
    ):
        try:
            remove_plugin(shortname)
            return _load_module(shortname, plugin_path)
        except BaseException:
            if previous is None:
                sys.modules.pop(module_key, None)
            else:
                sys.modules[module_key] = previous
            raise


def _load_module(shortname, plugin_path=None):
    if shortname.startswith("__"):
        pass
    elif shortname.endswith("_"):
        load_module_sortner(shortname)
    else:
        if plugin_path is None:
            path = Path(f"userbot/plugins/{shortname}.py")
            name = f"userbot.plugins.{shortname}"
        else:
            path = Path((f"{plugin_path}/{shortname}.py"))
            name = f"{plugin_path}/{shortname}".replace("/", ".")
        checkplugins(path)
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        mod.bot = catub
        mod.LOGS = LOGS
        mod.Config = Config
        mod._format = _format
        mod.sudo_cmd = sudo_cmd
        mod.CMD_HELP = CMD_HELP
        mod.reply_id = reply_id
        mod.admin_cmd = admin_cmd
        mod._catutils = _catutils
        mod.edit_delete = edit_delete
        mod.install_pip = install_pip
        mod.parse_pre = _format.parse_pre
        mod.edit_or_reply = edit_or_reply
        mod.tgbot = catub.tgbot
        mod.logger = logging.getLogger(shortname)
        mod.borg = catub
        sys.modules[f"userbot.plugins.{shortname}"] = mod
        # Reload must see the current bytes even for same-size edits made within
        # one filesystem timestamp tick (timestamp-based pyc validation cannot).
        exec(compile(path.read_bytes(), str(path), "exec"), mod.__dict__)
        # for imports
        sys.modules[f"userbot.plugins.{shortname}"] = mod
        LOGS.info(f"Successfully imported {shortname}")


def load_module_sortner(shortname):
    path = Path(f"userbot/plugins/{shortname}.py")
    checkplugins(path)
    name = f"userbot.plugins.{shortname}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    exec(compile(path.read_bytes(), str(path), "exec"), mod.__dict__)
    LOGS.info(f"Successfully imported {shortname}")


def remove_plugin(shortname):
    module = sys.modules.get(f"userbot.plugins.{shortname}")
    names = {f"userbot.plugins.{shortname}"}
    if module is not None:
        names.add(module.__name__)

    def owned(callback):
        return getattr(callback, "__module__", None) in names

    for client in (catub, getattr(catub, "tgbot", None)):
        if client is not None:
            for callback, builder in list(client.list_event_handlers()):
                if owned(callback):
                    client.remove_event_handler(callback, builder)
    for key, callbacks in list(LOADED_CMDS.items()):
        remaining = [cb for cb in callbacks if not owned(cb)]
        if remaining:
            LOADED_CMDS[key] = remaining
        else:
            del LOADED_CMDS[key]
    commands = PLG_INFO.pop(shortname, [])
    for command in commands:
        if not any(command in cmds for cmds in PLG_INFO.values()):
            CMD_INFO.pop(command, None)
    for group, plugins in list(GRP_INFO.items()):
        GRP_INFO[group] = [p for p in plugins if p != shortname]
        if not GRP_INFO[group]:
            del GRP_INFO[group]
            if group in BOT_INFO:
                BOT_INFO.remove(group)
    LOAD_PLUG.pop(shortname, None)
    CMD_HELP.pop(shortname, None)
    removed = {key for key, handler in atomic_registry._handlers.items()
               if getattr(handler, "plugin_name", None) == shortname}
    for key in removed:
        del atomic_registry._handlers[key]
    for command, key in list(atomic_registry._command_map.items()):
        if key in removed:
            del atomic_registry._command_map[command]
    return True


def checkplugins(filename):
    try:
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            filedata = f.read()
        modified = filedata.replace("sendmessage", "send_message")
        modified = modified.replace("sendfile", "send_file")
        modified = modified.replace("editmessage", "edit_message")
        if modified != filedata:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(modified)
    except Exception as e:
        LOGS.debug("checkplugins error on %s: %s", filename, e)
