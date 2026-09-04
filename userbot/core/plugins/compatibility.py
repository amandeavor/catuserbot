# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import inspect
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import logging

from .registry import RegisteredHandler, atomic_registry

LOGS = logging.getLogger("Aetheris.Compatibility")


def register_legacy_command(
    client: Any,
    callback: Callable[..., Any],
    pattern: Optional[str] = None,
    command: Optional[Union[str, Tuple[str, str]]] = None,
    groups_only: bool = False,
    private_only: bool = False,
    allow_sudo: bool = True,
    event_builder: Optional[Any] = None,
) -> None:
    """
    Registers a legacy CatUserBot/Aetheris v4 command handler into the V5 Atomic Registry.
    Extracts plugin ownership from caller stack frame and binds lifecycle tracking.
    """
    stack = inspect.stack()
    caller_frame = stack[2] if len(stack) > 2 else stack[1]
    caller_file = Path(caller_frame.filename).stem.replace(".py", "")

    cmd_name = None
    category = "utils"
    if command:
        if isinstance(command, (list, tuple)):
            cmd_name = command[0]
            if len(command) > 1:
                category = command[1]
        else:
            cmd_name = str(command)
    elif pattern:
        # Extract word from pattern regex
        clean = pattern.lstrip("^\\#.").split("(")[0].strip()
        if clean:
            cmd_name = clean

    handler_id = f"{caller_file}:{cmd_name or callback.__name__}:{id(callback)}"
    compiled_pattern = re.compile(pattern) if pattern else None

    reg_handler = RegisteredHandler(
        handler_id=handler_id,
        plugin_name=caller_file,
        generation_key=f"{caller_file}@legacy",
        pattern=compiled_pattern,
        callback=callback,
        is_command=True,
        command_name=cmd_name,
        category=category,
        allow_sudo=allow_sudo,
        groups_only=groups_only,
        private_only=private_only,
        event_builder=event_builder,
    )

    # Register into atomic registry asynchronously if loop running, or store directly
    atomic_registry._handlers[handler_id] = reg_handler
    if cmd_name:
        atomic_registry._command_map[cmd_name.lower()] = handler_id
    LOGS.debug("Compatibility registered command: %s (plugin: %s)", cmd_name, caller_file)
