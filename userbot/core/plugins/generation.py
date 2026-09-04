# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .manifest import PluginManifest


class PluginGeneration:
    """Represents an isolated, versioned generation of an active plugin."""

    def __init__(
        self,
        name: Optional[str] = None,
        generation_id: int = 1,
        manifest: Optional[PluginManifest] = None,
        module: Optional[Any] = None,
        container: Optional[Any] = None,
    ):
        self.manifest = manifest or PluginManifest(name=name or "plugin", version="1.0.0")
        self.name = name or self.manifest.name
        self.generation_id = generation_id
        self.generation_key = f"{self.name}@gen_{generation_id}"
        self.module = module
        self.container = container
        self.created_at = time.time()
        self.is_active = False
        self.is_quiesced = False
        self.handlers: List[Tuple[Any, Callable[..., Any]]] = []
        self.tasks: Set[asyncio.Task] = set()
        self.state: Dict[str, Any] = {}
        self.logger = logging.getLogger(f"plugin.{self.generation_key}")
        self.on_load_fn: Optional[Callable[..., Any]] = None
        self.on_quiesce_fn: Optional[Callable[..., Any]] = None
        self.on_unload_fn: Optional[Callable[..., Any]] = None

    def track_task(self, task: asyncio.Task) -> asyncio.Task:
        """Track an asynchronous task owned by this generation."""
        self.tasks.add(task)
        task.add_done_callback(lambda t: self.tasks.discard(t))
        return task

    async def cancel_and_drain_tasks(self, timeout: float = 3.0) -> None:
        """Cancel and drain all background tasks owned by this generation."""
        if not self.tasks:
            return

        for t in list(self.tasks):
            if not t.done():
                t.cancel()

        pending = [t for t in self.tasks if not t.done()]
        if pending:
            await asyncio.wait(pending, timeout=timeout)
        self.tasks.clear()

    async def activate(self) -> None:
        self.is_active = True
        if self.on_load_fn:
            res = self.on_load_fn(self.container)
            if asyncio.iscoroutine(res):
                await res

    async def quiesce(self) -> None:
        self.is_quiesced = True
        if self.on_quiesce_fn:
            res = self.on_quiesce_fn(self.container)
            if asyncio.iscoroutine(res):
                await res
        await self.run_quiesce()

    async def unload(self) -> None:
        self.is_active = False
        if self.on_unload_fn:
            res = self.on_unload_fn(self.container)
            if asyncio.iscoroutine(res):
                await res
        await self.run_unload()

    async def export_state(self) -> Dict[str, Any]:
        """Export state from this generation for migration to the next generation."""
        exported = dict(self.state)
        if self.module and hasattr(self.module, "export_state"):
            try:
                mod_state = self.module.export_state()
                if asyncio.iscoroutine(mod_state):
                    mod_state = await mod_state
                if isinstance(mod_state, dict):
                    exported.update(mod_state)
            except Exception as e:
                self.logger.warning("Error calling export_state on %s: %s", self.generation_key, e)
        return exported

    async def import_state(self, state: Dict[str, Any]) -> None:
        """Import state from a previous generation."""
        self.state.update(state)
        if self.module and hasattr(self.module, "import_state"):
            try:
                res = self.module.import_state(state)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                self.logger.warning("Error calling import_state on %s: %s", self.generation_key, e)

    async def run_quiesce(self) -> None:
        """Notify plugin generation to stop accepting new work."""
        self.is_quiesced = True
        if self.module and hasattr(self.module, "on_quiesce"):
            try:
                res = self.module.on_quiesce()
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                self.logger.error("Error during on_quiesce in %s: %s", self.generation_key, e)

    async def run_unload(self) -> None:
        """Run cleanup lifecycle on generation."""
        self.is_active = False
        if self.module and hasattr(self.module, "on_unload"):
            try:
                res = self.module.on_unload()
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                self.logger.error("Error during on_unload in %s: %s", self.generation_key, e)
