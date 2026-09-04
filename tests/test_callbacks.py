# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import time
from unittest.mock import AsyncMock
import pytest
from userbot.core.callbacks import SecureCallbackManager


@pytest.mark.asyncio
async def test_secure_callback_creation_and_handling():
    mgr = SecureCallbackManager()

    called = False

    async def mock_handler(event, token):
        nonlocal called
        called = True
        assert token.payload.get("page") == 2

    mgr.register_handler("paginate", mock_handler)

    token_str = mgr.create_token(
        action="paginate",
        payload={"page": 2},
        allowed_user_ids={123456},
        ttl=60.0,
    )
    assert token_str.startswith("cb:")

    # Authorized event
    mock_event = AsyncMock()
    mock_event.data = token_str.encode("utf-8")
    mock_event.sender_id = 123456

    handled = await mgr.handle_callback_query(mock_event)
    assert handled is True
    assert called is True


@pytest.mark.asyncio
async def test_callback_unauthorized_user_rejection():
    mgr = SecureCallbackManager()

    token_str = mgr.create_token(
        action="admin_action",
        payload={},
        allowed_user_ids={999},
    )

    mock_event = AsyncMock()
    mock_event.data = token_str.encode("utf-8")
    mock_event.sender_id = 111  # Unauthorized

    handled = await mgr.handle_callback_query(mock_event)
    assert handled is True
    mock_event.answer.assert_called_with("⛔ Access Denied: You cannot trigger this action.", alert=True)


@pytest.mark.asyncio
async def test_callback_single_use():
    mgr = SecureCallbackManager()

    call_count = 0

    async def handler(event, token):
        nonlocal call_count
        call_count += 1

    mgr.register_handler("confirm", handler)
    token_str = mgr.create_token(action="confirm", single_use=True)

    mock_event = AsyncMock()
    mock_event.data = token_str.encode("utf-8")
    mock_event.sender_id = 123

    # First call succeeds
    await mgr.handle_callback_query(mock_event)
    assert call_count == 1

    # Second call fails because token was single-use
    await mgr.handle_callback_query(mock_event)
    assert call_count == 1
    mock_event.answer.assert_called_with("⚠️ This button session has expired or is invalid.", alert=True)


def test_callback_data_size_strict_limits():
    """
    Section 16: Telegram MTProto strictly limits inline callback_data to 1-64 bytes.
    Verify that generated tokens NEVER exceed 64 bytes even with massive actions or payload metadata.
    """
    mgr = SecureCallbackManager()

    # Test 1000 generated tokens
    for i in range(1000):
        large_payload = {f"k_{j}": f"v_{j}" * 50 for j in range(20)}
        token_str = mgr.create_token(
            action=f"heavy_action_name_that_is_very_long_{i}",
            payload=large_payload,
            allowed_user_ids={123456, 789012},
        )

        encoded_bytes = token_str.encode("utf-8")
        byte_len = len(encoded_bytes)

        # Telegram MTProto constraint: 1 <= len(callback_data) <= 64 bytes
        assert 1 <= byte_len <= 64, f"Token {token_str} has length {byte_len}, which exceeds 64 bytes!"
        assert token_str.startswith("cb:")
