"""Real loader and Telethon registrations; application dependencies are isolated."""
import importlib.util
import logging
import os
import sys
import types
from pathlib import Path

import pytest
import pytest_asyncio
from telethon import TelegramClient, events
from telethon.sessions import MemorySession

ROOT = Path(__file__).resolve().parents[2]


@pytest_asyncio.fixture
async def loader(monkeypatch, tmp_path):
    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        mod.__path__ = []
        monkeypatch.setitem(sys.modules, name, mod)
        return mod

    bot = TelegramClient(MemorySession(), 12345, "0" * 32)
    bot.tgbot = TelegramClient(MemorySession(), 12345, "0" * 32)
    module("userbot", CMD_HELP={}, LOAD_PLUG={})
    module("userbot.utils")
    core = module("userbot.core", BOT_INFO=[], CMD_INFO={}, GRP_INFO={}, LOADED_CMDS={}, PLG_INFO={})
    module("userbot.core.plugins")
    registry = types.SimpleNamespace(_handlers={}, _command_map={})
    module("userbot.core.plugins.registry", atomic_registry=registry)
    module("userbot.Config", Config=object())
    module("userbot.core.logger", logging=logging)
    module("userbot.core.managers", edit_delete=None, edit_or_reply=None)
    module("userbot.core.session", catub=bot)
    module("userbot.helpers")
    module("userbot.helpers.utils", _catutils=None, _format=types.SimpleNamespace(parse_pre=None), install_pip=None, reply_id=None)
    module("userbot.utils.decorators", admin_cmd=None, sudo_cmd=None)

    def real_module(name, relative):
        spec = importlib.util.spec_from_file_location(name, ROOT / relative)
        mod = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, mod)
        spec.loader.exec_module(mod)
        return mod

    real_module("userbot.core.plugins.legacy_reload", "userbot/core/plugins/legacy_reload.py")
    manager = real_module("userbot.utils.pluginmanager", "userbot/utils/pluginmanager.py")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "userbot/plugins").mkdir(parents=True)
    monkeypatch.setitem(sys.modules, "userbot.plugins.probe", None)
    return manager, bot, core, tmp_path / "userbot/plugins/probe.py"


def plugin(version, fail=False):
    return f'''
from telethon import events
from userbot.core import PLG_INFO, LOADED_CMDS, CMD_INFO
async def command(event):
    event.append({version!r})
async def watcher(event):
    event.append("watch:" + {version!r})
bot.add_event_handler(command, events.NewMessage(pattern="probe"))
bot.add_event_handler(watcher, events.NewMessage())
tgbot.add_event_handler(command, events.NewMessage())
PLG_INFO["probe"] = ["probe"]
LOADED_CMDS.setdefault("probe", []).extend([command, watcher])
CMD_INFO["probe"] = [{version!r}]
''' + ('raise RuntimeError("import failed after registration")\n' if fail else '')


@pytest.mark.asyncio
async def test_failed_import_restores_both_clients_and_metadata(loader):
    manager, bot, core, path = loader
    path.write_text(plugin("original"))
    manager.load_module("probe")
    old = list(bot.list_event_handlers())
    old_bot = list(bot.tgbot.list_event_handlers())
    old_module = sys.modules["userbot.plugins.probe"]
    path.write_text(plugin("replacement-that-fails", fail=True))
    with pytest.raises(RuntimeError):
        manager.load_module("probe")
    assert bot.list_event_handlers() == old
    assert bot.tgbot.list_event_handlers() == old_bot
    assert sys.modules["userbot.plugins.probe"] is old_module
    assert core.CMD_INFO == {"probe": ["original"]}
    output = []
    for callback, _ in bot.list_event_handlers():
        await callback(output)
    assert output == ["original", "watch:original"]


@pytest.mark.asyncio
async def test_reload_and_unload_remove_commands_watchers_and_assistant(loader):
    manager, bot, core, path = loader
    path.write_text(plugin("original"))
    manager.load_module("probe")
    stamp = path.stat()
    path.write_text(plugin("new-code"))
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    manager.load_module("probe")
    output = []
    for callback, _ in bot.list_event_handlers():
        await callback(output)
    assert output == ["new-code", "watch:new-code"]
    assert len(bot.tgbot.list_event_handlers()) == 1
    assert len(core.LOADED_CMDS["probe"]) == 2
    manager.remove_plugin("probe")
    assert bot.list_event_handlers() == bot.tgbot.list_event_handlers() == []
    assert not core.LOADED_CMDS and not core.PLG_INFO and not core.CMD_INFO


@pytest.mark.asyncio
async def test_unload_preserves_another_plugins_colliding_command(loader):
    manager, bot, core, path = loader
    path.write_text(plugin("original"))
    manager.load_module("probe")
    async def unrelated(event):
        pass
    unrelated.__module__ = "userbot.plugins.other"
    bot.add_event_handler(unrelated, events.NewMessage())
    core.LOADED_CMDS["probe"].append(unrelated)
    core.PLG_INFO["other"] = ["probe"]
    manager.remove_plugin("probe")
    assert [cb for cb, _ in bot.list_event_handlers()] == [unrelated]
    assert core.LOADED_CMDS["probe"] == [unrelated]
    assert "probe" in core.CMD_INFO
