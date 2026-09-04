# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import gc
import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..container import container
from ..jobs.supervisor import job_supervisor
from .generation import PluginGeneration
from .manifest import PluginManifest
from .registry import RegisteredHandler, atomic_registry

LOGS = logging.getLogger("Aetheris.PluginManager")


class VersionedPluginManager:
    """
    Production Zero-Downtime Transactional Plugin Host for Aetheris V5.
    Manages isolated plugin generations and executes 16-step atomic swaps.
    """

    def __init__(self):
        self._active_generations: Dict[str, PluginGeneration] = {}
        self._generation_counters: Dict[str, int] = {}
        self._plugin_paths: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    def get_generation(self, plugin_name: str) -> Optional[PluginGeneration]:
        return self._active_generations.get(plugin_name)

    def list_plugins(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "generation": gen.generation_id,
                "key": gen.generation_key,
                "version": gen.manifest.version,
                "handlers": len(gen.handlers),
                "tasks": len(gen.tasks),
                "is_active": gen.is_active,
            }
            for name, gen in self._active_generations.items()
        ]

    async def load_plugin(
        self,
        plugin_name: str,
        file_path: Optional[str] = None,
        manifest: Optional[PluginManifest] = None,
    ) -> PluginGeneration:
        """Loads a plugin module into a new generation and registers it atomically."""
        async with self._lock:
            return await self._load_plugin_internal(plugin_name, file_path, manifest)

    async def _load_plugin_internal(
        self,
        plugin_name: str,
        file_path: Optional[str] = None,
        manifest: Optional[PluginManifest] = None,
    ) -> PluginGeneration:
        if file_path:
            self._plugin_paths[plugin_name] = file_path
        else:
            file_path = self._plugin_paths.get(plugin_name)

        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"Plugin file not found for: {plugin_name} at {file_path}")

        gen_id = self._generation_counters.get(plugin_name, 0) + 1
        self._generation_counters[plugin_name] = gen_id
        effective_manifest = manifest or PluginManifest(name=plugin_name)

        # 1. Prepare isolated module specification
        mod_name = f"aetheris.plugins.{plugin_name}_gen{gen_id}"
        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load module specification for {file_path}")

        module = importlib.util.module_from_spec(spec)
        generation = PluginGeneration(
            name=plugin_name,
            generation_id=gen_id,
            manifest=effective_manifest,
            module=module,
        )

        # 2. Inject scoped V5 PluginContext
        ctx = container.create_plugin_context(plugin_name, gen_id)
        setattr(module, "ctx", ctx)
        setattr(module, "generation", generation)

        # 3. Execute module code in isolated namespace
        try:
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
        except Exception as e:
            sys.modules.pop(mod_name, None)
            LOGS.error("Failed to execute plugin module %s: %s", mod_name, e)
            raise

        # 4. Invoke V5 lifecycle hook if present
        if hasattr(module, "on_load"):
            try:
                res = module.on_load(ctx)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                sys.modules.pop(mod_name, None)
                LOGS.error("on_load hook failed for %s: %s", generation.generation_key, e)
                raise

        generation.is_active = True
        self._active_generations[plugin_name] = generation
        LOGS.info("Loaded plugin generation: %s (%d handlers)", generation.generation_key, len(generation.handlers))
        return generation

    async def reload_plugin(self, plugin_name: str) -> PluginGeneration:
        """
        Executes the transactional 16-step zero-downtime hot reload.
        Maintains uninterrupted MTProto connection and atomically swaps handlers.
        """
        async with self._lock:
            old_generation = self._active_generations.get(plugin_name)
            old_state = {}

            # Step 1-2: Export state from old generation if active
            if old_generation:
                LOGS.debug("Step 1: Exporting state from %s", old_generation.generation_key)
                old_state = old_generation.export_state()

            # Step 3-7: Load new generation in isolated namespace
            LOGS.debug("Step 3-7: Preparing new generation for %s", plugin_name)
            new_generation = await self._load_plugin_internal(plugin_name)

            # Step 8: Import old state into new generation
            if old_state:
                LOGS.debug("Step 8: Importing state into %s", new_generation.generation_key)
                new_generation.import_state(old_state)

            # Step 9-11: Quiesce old generation and swap handlers atomically
            if old_generation:
                LOGS.debug("Step 9-11: Quiescing and draining %s", old_generation.generation_key)
                await old_generation.run_quiesce()
                await atomic_registry.unregister_generation(old_generation.generation_key)
                await old_generation.cancel_and_drain_tasks(timeout=2.0)
                await job_supervisor.cancel_plugin_jobs(plugin_name)
                await old_generation.run_unload()

                # Step 12-16: Clean module references and garbage collect
                old_mod_name = f"aetheris.plugins.{plugin_name}_gen{old_generation.generation_id}"
                sys.modules.pop(old_mod_name, None)
                old_generation.module = None
                gc.collect()

            LOGS.info("Successfully reloaded %s -> %s with zero downtime", plugin_name, new_generation.generation_key)
            return new_generation

    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unloads a plugin, unbinds all handlers, and frees resources."""
        async with self._lock:
            generation = self._active_generations.pop(plugin_name, None)
            if not generation:
                return False

            await generation.run_quiesce()
            await atomic_registry.unregister_generation(generation.generation_key)
            await generation.cancel_and_drain_tasks(timeout=2.0)
            await job_supervisor.cancel_plugin_jobs(plugin_name)
            await generation.run_unload()

            mod_name = f"aetheris.plugins.{plugin_name}_gen{generation.generation_id}"
            sys.modules.pop(mod_name, None)
            generation.module = None
            gc.collect()

            LOGS.info("Unloaded plugin: %s", plugin_name)
            return True


plugin_manager = VersionedPluginManager()
