# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Pattern, Set

from ..transport.interface import ITelegramTransport

LOGS = logging.getLogger("Aetheris.Registry")


@dataclass
class HandlerBinding:
    command_name: str
    handler: Callable[..., Any]
    pattern: Optional[str] = None
    generation_id: int = 1


@dataclass
class RegisteredHandler:
    """Represents a registered command or watcher owned by a plugin generation."""
    handler_id: str
    plugin_name: str
    generation_key: str
    pattern: Optional[Pattern]
    callback: Callable[..., Any]
    is_command: bool = True
    command_name: Optional[str] = None
    category: str = "utils"
    description: str = ""
    allow_sudo: bool = True
    groups_only: bool = False
    private_only: bool = False
    event_builder: Optional[Any] = None
    bound_transport_handler: Optional[Any] = None
    generation_id: int = 1


class AtomicHandlerRegistry:
    """
    Centralized, atomic event and command handler registry for Aetheris V5.
    Guarantees deterministic unbinding and prevents zombie/ghost callbacks.
    """

    def __init__(self, transport: Optional[ITelegramTransport] = None):
        self._transport = transport
        self._handlers: Dict[str, Any] = {}
        self._command_map: Dict[str, str] = {}  # cmd_name -> handler_id
        self._lock = asyncio.Lock()

    @property
    def handlers(self) -> List[Any]:
        return list(self._handlers.values())

    def set_transport(self, transport: ITelegramTransport) -> None:
        self._transport = transport

    def register(
        self,
        command_name: str,
        handler: Callable[..., Any],
        generation_id: int = 1,
        pattern: Optional[str] = None,
    ) -> HandlerBinding:
        binding = HandlerBinding(
            command_name=command_name,
            handler=handler,
            pattern=pattern,
            generation_id=generation_id,
        )
        key = f"{command_name}@gen_{generation_id}"
        self._handlers[key] = binding
        self._command_map[command_name.lower()] = key
        return binding

    def atomic_swap_generation(
        self,
        old_gen_id: int,
        new_gen_id: int,
        new_bindings: List[HandlerBinding],
    ) -> None:
        # Unregister old generation handlers
        to_remove = [k for k, v in self._handlers.items() if getattr(v, "generation_id", None) == old_gen_id]
        for k in to_remove:
            self._handlers.pop(k, None)

        # Register new generation bindings
        for b in new_bindings:
            k = f"{b.command_name}@gen_{new_gen_id}"
            self._handlers[k] = b
            self._command_map[b.command_name.lower()] = k

    async def register_handler(self, handler: RegisteredHandler) -> None:
        """Register a handler and optionally bind to transport."""
        async with self._lock:
            self._handlers[handler.handler_id] = handler
            if handler.command_name:
                self._command_map[handler.command_name.lower()] = handler.handler_id

            if self._transport and handler.event_builder:
                try:
                    self._transport.add_event_handler(handler.callback, handler.event_builder)
                    handler.bound_transport_handler = handler.callback
                except Exception as e:
                    LOGS.error("Error binding handler %s to transport: %s", handler.handler_id, e)

    async def unregister_generation(self, generation_key: str) -> List[str]:
        """Atomically unregister all handlers belonging to a specific generation."""
        removed_ids = []
        async with self._lock:
            to_remove = [
                hid for hid, h in self._handlers.items()
                if getattr(h, "generation_key", None) == generation_key
            ]
            for hid in to_remove:
                handler = self._handlers.pop(hid)
                if getattr(handler, "command_name", None) and handler.command_name.lower() in self._command_map:
                    if self._command_map[handler.command_name.lower()] == hid:
                        del self._command_map[handler.command_name.lower()]

                if self._transport and getattr(handler, "bound_transport_handler", None):
                    try:
                        self._transport.remove_event_handler(
                            handler.bound_transport_handler,
                            handler.event_builder,
                        )
                    except Exception as e:
                        LOGS.debug("Exception during transport handler removal: %s", e)

                removed_ids.append(hid)

        LOGS.debug("Unregistered %d handlers for generation %s", len(removed_ids), generation_key)
        return removed_ids

    async def unregister_plugin(self, plugin_name: str) -> List[str]:
        """Atomically unregister all handlers belonging to a specific plugin."""
        removed_ids = []
        async with self._lock:
            to_remove = [
                hid for hid, h in self._handlers.items()
                if getattr(h, "plugin_name", None) == plugin_name
            ]
            for hid in to_remove:
                handler = self._handlers.pop(hid)
                if getattr(handler, "command_name", None) and handler.command_name.lower() in self._command_map:
                    if self._command_map[handler.command_name.lower()] == hid:
                        del self._command_map[handler.command_name.lower()]

                if self._transport and getattr(handler, "bound_transport_handler", None):
                    try:
                        self._transport.remove_event_handler(
                            handler.bound_transport_handler,
                            handler.event_builder,
                        )
                    except Exception as e:
                        LOGS.debug("Exception during transport handler removal: %s", e)

                removed_ids.append(hid)

        LOGS.debug("Unregistered %d handlers for plugin %s", len(removed_ids), plugin_name)
        return removed_ids

    def get_handler_for_command(self, cmd_name: str) -> Optional[Any]:
        hid = self._command_map.get(cmd_name.lower())
        return self._handlers.get(hid) if hid else None

    def list_handlers_for_plugin(self, plugin_name: str) -> List[Any]:
        return [h for h in self._handlers.values() if getattr(h, "plugin_name", None) == plugin_name]

    def total_handlers(self) -> int:
        return len(self._handlers)

    def total_commands(self) -> int:
        return len(self._command_map)


atomic_registry = AtomicHandlerRegistry()
