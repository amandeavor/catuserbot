# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

from dataclasses import dataclass
from typing import Any, Dict, Optional
import logging

from .transport.interface import ITelegramTransport


@dataclass
class PluginContext:
    """Scoped execution context injected into Aetheris V5 plugins."""
    plugin_name: str
    generation: int
    telegram: ITelegramTransport
    db: Any
    cache: Any
    jobs: Any
    ai: Any
    media: Any
    config: Any
    logger: logging.Logger
    permissions: Any

    def get_service(self, name: str) -> Optional[Any]:
        return getattr(self, name, None)


class ServiceContainer:
    """Central dependency injection container for Aetheris V5 runtime services."""

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._logger = logging.getLogger("Aetheris.Container")

    def register(self, name: str, service: Any) -> None:
        """Register a service in the container."""
        self._services[name] = service
        self._logger.debug("Registered service: %s", name)

    def get(self, name: str, default: Optional[Any] = None) -> Any:
        """Retrieve a service by name."""
        return self._services.get(name, default)

    def create_plugin_context(self, plugin_name: str, generation: int = 1) -> PluginContext:
        """Create an isolated, scoped context for a plugin generation."""
        logger = logging.getLogger(f"plugin.{plugin_name}.gen_{generation}")
        return PluginContext(
            plugin_name=plugin_name,
            generation=generation,
            telegram=self.get("telegram"),
            db=self.get("db"),
            cache=self.get("cache"),
            jobs=self.get("jobs"),
            ai=self.get("ai"),
            media=self.get("media"),
            config=self.get("config"),
            logger=logger,
            permissions=self.get("permissions"),
        )


container = ServiceContainer()
