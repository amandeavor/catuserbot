# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class PluginCapability:
    TELEGRAM_READ = "telegram.read"
    TELEGRAM_SEND = "telegram.send"
    TELEGRAM_DELETE = "telegram.delete"
    TELEGRAM_ADMIN = "telegram.admin"
    STORAGE_PLUGIN = "storage.plugin"
    FILESYSTEM_TEMP = "filesystem.temp"
    NETWORK_HTTP = "network.http"
    MEDIA_FFMPEG = "media.ffmpeg"
    AI_CLOUD = "ai.cloud"
    AI_LOCAL = "ai.local"

    DEFAULT_BUILTIN = {
        TELEGRAM_READ,
        TELEGRAM_SEND,
        TELEGRAM_DELETE,
        STORAGE_PLUGIN,
        FILESYSTEM_TEMP,
        NETWORK_HTTP,
    }


@dataclass
class PluginManifest:
    """Metadata and capability declarations for Aetheris V5 plugins."""
    name: str
    version: str = "5.0.0"
    author: str = "Aetheris"
    description: str = ""
    capabilities: Set[str] = field(default_factory=lambda: set(PluginCapability.DEFAULT_BUILTIN))
    dependencies: List[str] = field(default_factory=list)
    min_aetheris_version: str = "5.0.0"
    commands: List[str] = field(default_factory=list)
    watchers: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    trusted: bool = True

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities
