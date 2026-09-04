# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import pytest
from userbot.core.container import ServiceContainer
from userbot.core.plugins.generation import PluginGeneration
from userbot.core.plugins.manifest import PluginManifest
from userbot.core.plugins.registry import AtomicHandlerRegistry


@pytest.mark.asyncio
async def test_plugin_generation_lifecycle():
    manifest = PluginManifest(
        name="test_plugin",
        version="1.0.0",
        description="Lifecycle test plugin",
    )
    container = ServiceContainer()
    gen = PluginGeneration(manifest=manifest, generation_id=1, container=container)

    lifecycle_events = []

    async def on_load(ctx):
        lifecycle_events.append("loaded")

    async def on_quiesce(ctx):
        lifecycle_events.append("quiesced")

    async def on_unload(ctx):
        lifecycle_events.append("unloaded")

    gen.on_load_fn = on_load
    gen.on_quiesce_fn = on_quiesce
    gen.on_unload_fn = on_unload

    await gen.activate()
    assert lifecycle_events == ["loaded"]

    await gen.quiesce()
    assert "quiesced" in lifecycle_events

    await gen.unload()
    assert "unloaded" in lifecycle_events


@pytest.mark.asyncio
async def test_plugin_state_migration_between_generations():
    manifest = PluginManifest(name="counter_plugin", version="1.0.0")
    container = ServiceContainer()

    gen1 = PluginGeneration(manifest=manifest, generation_id=1, container=container)
    gen1.state = {"counter": 42, "user_flag": True}

    exported_state = await gen1.export_state()
    assert exported_state == {"counter": 42, "user_flag": True}

    # Next generation
    manifest_v2 = PluginManifest(name="counter_plugin", version="2.0.0")
    gen2 = PluginGeneration(manifest=manifest_v2, generation_id=2, container=container)
    await gen2.import_state(exported_state)

    assert gen2.state["counter"] == 42
    assert gen2.state["user_flag"] is True


@pytest.mark.asyncio
async def test_atomic_handler_registry_swap():
    registry = AtomicHandlerRegistry()

    def dummy_handler_v1(event):
        return "v1"

    def dummy_handler_v2(event):
        return "v2"

    # Register in gen 1
    registry.register(command_name="ping", handler=dummy_handler_v1, generation_id=1)
    assert len(registry.handlers) == 1
    assert registry.handlers[0].handler(None) == "v1"

    # Atomic swap to gen 2
    from userbot.core.plugins.registry import HandlerBinding
    new_binding = HandlerBinding(
        command_name="ping",
        handler=dummy_handler_v2,
        pattern=r"\.ping",
        generation_id=2,
    )
    registry.atomic_swap_generation(old_gen_id=1, new_gen_id=2, new_bindings=[new_binding])

    assert len(registry.handlers) == 1
    assert registry.handlers[0].handler(None) == "v2"
    assert registry.handlers[0].generation_id == 2
