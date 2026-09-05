from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telethon import events, types


@pytest.mark.asyncio
@pytest.mark.parametrize("incoming", [True, False])
@pytest.mark.parametrize("result", ["admin", "member", "error"])
async def test_admin_filter_awaits_permission_and_fails_closed(monkeypatch, incoming, result):
    from userbot.core import events as filters
    monkeypatch.setattr(events.NewMessage, "filter", lambda self, event: event)
    reply = AsyncMock()
    monkeypatch.setattr(filters, "edit_or_reply", reply)
    lookup = AsyncMock(return_value=SimpleNamespace(is_creator=False, is_admin=result == "admin"))
    if result == "error":
        lookup.side_effect = ConnectionError("unavailable")
    event = SimpleNamespace(
        message=SimpleNamespace(via_bot_id=None), _chat_peer=types.PeerChannel(12),
        _client=SimpleNamespace(get_permissions=lookup), chat_id=-10012, sender_id=7,
    )
    builder = filters.NewMessage(require_admin=True, incoming=incoming)
    accepted = await builder.filter(event)
    assert (accepted is event) == (result == "admin")
    lookup.assert_awaited_once_with(-10012, 7 if incoming else "me")
    assert reply.await_count == (1 if result == "member" else 0)


@pytest.mark.asyncio
async def test_async_base_filter_cannot_be_bypassed(monkeypatch):
    from userbot.core import events as filters
    monkeypatch.setattr(events.NewMessage, "filter", AsyncMock(return_value=False))
    assert await filters.NewMessage().filter(SimpleNamespace()) is None
