# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

from .compatibility import register_legacy_command
from .generation import PluginGeneration
from .manager import VersionedPluginManager, plugin_manager
from .manifest import PluginCapability, PluginManifest
from .registry import AtomicHandlerRegistry, RegisteredHandler, atomic_registry

__all__ = [
    "PluginManifest",
    "PluginCapability",
    "PluginGeneration",
    "RegisteredHandler",
    "AtomicHandlerRegistry",
    "atomic_registry",
    "VersionedPluginManager",
    "plugin_manager",
    "register_legacy_command",
]
