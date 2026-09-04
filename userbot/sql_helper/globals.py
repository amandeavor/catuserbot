# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import threading
import time
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import Column, String, UnicodeText

from . import BASE, ENGINE, SESSION


class Globals(BASE):
    __tablename__ = "globals"
    __table_args__ = {"extend_existing": True}
    variable = Column(String, primary_key=True, nullable=False)
    value = Column(UnicodeText, primary_key=True, nullable=False)

    def __init__(self, variable, value):
        self.variable = str(variable)
        self.value = value


try:
    Globals.__table__.create(bind=ENGINE, checkfirst=True)
except Exception:
    pass

# Thread-safe in-memory cache to eliminate event loop blocking on high-frequency reads
_CACHE: Dict[str, Tuple[Optional[str], float]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 300.0  # 5 minutes TTL for cached values


def gvarstatus(variable: str) -> Optional[str]:
    """Retrieve global variable with thread-safe in-memory caching."""
    now = time.time()
    var_str = str(variable)

    with _CACHE_LOCK:
        if var_str in _CACHE:
            val, exp = _CACHE[var_str]
            if now < exp:
                return val

    # Cache miss: query database
    val = None
    try:
        row = (
            SESSION.query(Globals)
            .filter(Globals.variable == var_str)
            .first()
        )
        if row:
            val = row.value
    except Exception:
        val = None
    finally:
        SESSION.close()

    with _CACHE_LOCK:
        _CACHE[var_str] = (val, now + _CACHE_TTL)

    return val


def addgvar(variable: str, value: Any) -> None:
    """Add or update a global variable and atomically invalidate the cache."""
    var_str = str(variable)
    val_str = str(value) if value is not None else ""

    try:
        if SESSION.query(Globals).filter(Globals.variable == var_str).one_or_none():
            delgvar(var_str)
        adder = Globals(var_str, val_str)
        SESSION.add(adder)
        SESSION.commit()
    except Exception:
        SESSION.rollback()
        raise
    finally:
        SESSION.close()

    with _CACHE_LOCK:
        _CACHE[var_str] = (val_str, time.time() + _CACHE_TTL)


def delgvar(variable: str) -> bool:
    """Delete a global variable and clear from cache."""
    var_str = str(variable)
    deleted = False

    try:
        rem = (
            SESSION.query(Globals)
            .filter(Globals.variable == var_str)
            .delete(synchronize_session="fetch")
        )
        SESSION.commit()
        deleted = bool(rem)
    except Exception:
        SESSION.rollback()
    finally:
        SESSION.close()

    with _CACHE_LOCK:
        _CACHE.pop(var_str, None)

    return deleted


def invalidate_cache(variable: Optional[str] = None) -> None:
    """Explicitly invalidate cache for a variable or clear all cached values."""
    with _CACHE_LOCK:
        if variable:
            _CACHE.pop(str(variable), None)
        else:
            _CACHE.clear()
