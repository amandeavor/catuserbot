# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris UserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import shlex
from typing import Any, Dict, List, Tuple


def parse_arguments(text: str) -> Tuple[Dict[str, Any], List[str], str]:
    """
    Parses CLI-style flags and positional arguments from message text.
    Supports:
        --flag value
        --flag=value
        -f value
        -abc (boolean flags grouped)
        --boolean-flag
    Returns: (flags_dict, positional_args_list, remaining_raw_text)
    """
    if not text:
        return {}, [], ""

    flags: Dict[str, Any] = {}
    positional: List[str] = []

    try:
        parts = shlex.split(text)
    except ValueError:
        parts = text.split()

    i = 0
    while i < len(parts):
        token = parts[i]
        if token.startswith("--"):
            key = token[2:]
            if "=" in key:
                k, v = key.split("=", 1)
                flags[k] = v
            elif i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                flags[key] = parts[i + 1]
                i += 1
            else:
                flags[key] = True
        elif token.startswith("-") and len(token) > 1 and not token[1].isdigit():
            key = token[1:]
            if len(key) == 1 and i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                flags[key] = parts[i + 1]
                i += 1
            else:
                for ch in key:
                    flags[ch] = True
        else:
            positional.append(token)
        i += 1

    remaining_raw = " ".join(positional)
    return flags, positional, remaining_raw
