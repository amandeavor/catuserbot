# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import pytest
from userbot.core.ai.interface import AIRequestOptions
from userbot.core.ai.memory import ConversationMemory
from userbot.core.ai.providers import MockAIProvider
from userbot.core.ai.router import AIRouterV5


@pytest.mark.asyncio
async def test_mock_provider_complete_and_stream():
    provider = MockAIProvider(name="mock_test")
    opts = AIRequestOptions(prompt="Hello Aetheris")

    resp = await provider.complete(opts)
    assert "Hello Aetheris" in resp.text
    assert resp.provider == "mock_test"
    assert resp.latency_ms > 0

    chunks = []
    async for chunk in provider.stream(opts):
        chunks.append(chunk)

    assert len(chunks) > 0
    assert "Hello" in "".join(chunks)


@pytest.mark.asyncio
async def test_conversation_memory():
    mem = ConversationMemory(max_history_per_chat=10)
    mem.add_turn("chat_1", "What is my name?", "Your name is Alice.")
    mem.add_turn("chat_1", "What did I ask?", "You asked about your name.")

    ctx = mem.get_context("chat_1")
    assert len(ctx) == 4
    assert ctx[0]["content"] == "What is my name?"

    mem.clear("chat_1")
    assert len(mem.get_context("chat_1")) == 0


@pytest.mark.asyncio
async def test_router_fallback_cascade():
    router = AIRouterV5()
    # Add a broken provider as primary
    class FailingProvider(MockAIProvider):
        async def complete(self, options):
            raise ConnectionError("Simulated API failure")

    failing = FailingProvider(name="broken_ai")
    router.register_provider(failing)
    router.set_priority_order(["broken_ai", "mock"])

    opts = AIRequestOptions(prompt="Testing fallback")
    res = await router.complete(opts)

    # Should have cascaded to 'mock'
    assert res.provider == "mock"
    assert "Testing fallback" in res.text
    # The broken provider's circuit should have recorded failure
    assert router.circuits["broken_ai"].failures >= 1
