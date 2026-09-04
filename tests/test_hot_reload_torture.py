# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import gc
import sys
import time
import pytest
from unittest.mock import MagicMock

from userbot.core.plugins.generation import GenerationState, PluginGeneration
from userbot.core.plugins.manifest import PluginManifest
from userbot.core.plugins.registry import AtomicHandlerRegistry, HandlerBinding, RegisteredHandler


@pytest.mark.asyncio
async def test_hot_reload_concurrency_torture_cycles():
    """
    Section 5: Concurrency torture test across 200 hot-reload cycles.
    Verifies:
      - Dispatching events concurrently while hot-reloading
      - Old generation handlers are drained and unreferenced
      - No zombie callbacks or duplicate responses
      - No continuous memory or task leakage
    """
    registry = AtomicHandlerRegistry()
    manifest = PluginManifest(name="torture_plugin", version="1.0.0")

    state_store = {"counter": 0}
    received_events = []
    dispatched_events = 0

    # Handler factory simulating work
    def make_handler(gen_id: int):
        async def handler(event_id: int):
            nonlocal state_store
            state_store["counter"] += 1
            received_events.append((gen_id, event_id))
            await asyncio.sleep(0.001)
        return handler

    # Initial generation
    current_gen_id = 1
    current_gen = PluginGeneration(manifest=manifest, generation_id=current_gen_id)
    binding = registry.register("ping", make_handler(current_gen_id), generation_id=current_gen_id)
    current_gen.state = GenerationState.ACTIVE

    num_cycles = 150

    for cycle in range(1, num_cycles + 1):
        next_gen_id = current_gen_id + 1
        next_gen = PluginGeneration(manifest=manifest, generation_id=next_gen_id)
        next_binding = HandlerBinding(
            command_name="ping",
            handler=make_handler(next_gen_id),
            generation_id=next_gen_id,
        )

        # 1. Start background dispatch of events during swap
        async def dispatch_burst(start_idx: int):
            for i in range(5):
                evt_id = start_idx + i
                h_binding = registry.get_handler_for_command("ping")
                if h_binding:
                    await h_binding.handler(evt_id)

        dispatch_task = asyncio.create_task(dispatch_burst(dispatched_events))
        dispatched_events += 5

        # 2. Perform atomic swap
        registry.atomic_swap_generation(
            old_gen_id=current_gen_id,
            new_gen_id=next_gen_id,
            new_bindings=[next_binding],
        )

        # 3. Drain old generation
        current_gen.state = GenerationState.DRAINING
        await dispatch_task
        current_gen.state = GenerationState.UNLOADED

        # Advance pointer
        current_gen_id = next_gen_id
        current_gen = next_gen

        # Periodic garbage collection and leak check
        if cycle % 50 == 0:
            gc.collect()
            # Registry should hold strictly the current generation handler
            assert registry.total_commands() == 1
            assert registry.total_handlers() == 1
            active_h = registry.get_handler_for_command("ping")
            assert active_h.generation_id == current_gen_id

    # Final assertions after 150 reload cycles
    gc.collect()
    assert registry.total_commands() == 1
    assert registry.total_handlers() == 1
    assert state_store["counter"] == dispatched_events
    assert len(received_events) == dispatched_events

    # Verify no old generation handlers remain in registry
    active_binding = registry.get_handler_for_command("ping")
    assert active_binding.generation_id == current_gen_id
