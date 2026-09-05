"""Invoke the callbacks actually registered by the production decorators offline."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telethon.sessions import MemorySession


@pytest.mark.asyncio
async def test_command_wrapper_executes_once_and_preserves_ownership(monkeypatch):
    from userbot.core import client, session
    bot = client.CatUserBotClient(MemorySession(), 12345, "0" * 32)
    monkeypatch.setattr(session, "catub", bot)
    for name in ("CMD_INFO", "PLG_INFO", "GRP_INFO", "LOADED_CMDS"):
        monkeypatch.setattr(client, name, {})
    monkeypatch.setattr(client, "BOT_INFO", [])
    called = []
    async def probe(event):
        "Probe documentation."
        called.append(event.raw_args)
    wrapper = bot.cat_cmd(pattern="auditprobe$", command=("auditprobe", "test"), edited=False, allow_sudo=False)(probe)
    callbacks = bot.list_event_handlers()
    assert len(callbacks) == 1
    assert callbacks[0][0] is wrapper
    assert wrapper.__module__ == probe.__module__
    await callbacks[0][0](SimpleNamespace(text=".auditprobe", chat_id=1))
    assert len(called) == 1


@pytest.mark.asyncio
async def test_bot_decorator_registers_its_error_wrapper(monkeypatch):
    from userbot.core import client, session
    bot = client.CatUserBotClient(MemorySession(), 12345, "0" * 32)
    bot.tgbot = client.CatUserBotClient(MemorySession(), 12345, "0" * 32)
    monkeypatch.setattr(session, "catub", bot)
    called = AsyncMock(side_effect=ValueError("probe error"))
    async def probe(event):
        await called(event)
    wrapper = bot.bot_cmd(disable_errors=True)(probe)
    assert bot.tgbot.list_event_handlers()[0][0] is wrapper
    await wrapper(SimpleNamespace())
    called.assert_awaited_once()
