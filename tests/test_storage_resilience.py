# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import pytest
from unittest.mock import patch
from sqlalchemy.exc import OperationalError

from userbot.sql_helper import (
    StorageMode,
    _resolve_storage_mode,
    check_connection,
    get_storage_mode,
    reconnect,
    start,
)
from userbot.sql_helper.globals import addgvar, delgvar, gvarstatus, invalidate_cache


def test_storage_mode_resolution():
    # Empty or None defaults to SQLite
    mode, uri = _resolve_storage_mode(None)
    assert mode == StorageMode.SQLITE
    assert "sqlite:///" in uri

    mode, uri = _resolve_storage_mode("")
    assert mode == StorageMode.SQLITE

    # Explicit SQLite uri
    mode, uri = _resolve_storage_mode("sqlite:///test.db")
    assert mode == StorageMode.SQLITE
    assert uri == "sqlite:///test.db"

    # PostgreSQL uri
    mode, uri = _resolve_storage_mode("postgres://user:pass@localhost:5432/mydb")
    assert mode == StorageMode.POSTGRESQL
    assert uri.startswith("postgresql://")


def test_refusal_of_silent_split_brain_fallback():
    """Verify that an unreachable PostgreSQL DB raises RuntimeError rather than silently switching to SQLite."""
    with patch("userbot.Config.Config.DB_URI", "postgresql://invalid_user:invalid_pass@127.0.0.1:59999/nonexistent"):
        with patch("userbot.sql_helper.create_engine") as mock_engine:
            mock_engine.side_effect = OperationalError("connection refused", {}, None)
            with pytest.raises(RuntimeError, match="strictly refuses to silently switch to SQLite"):
                start()


def test_database_cached_reads_during_temporary_outage():
    """Verify that cache serves reads even if the DB session temporarily fails."""
    key = "resilience_test_key"
    val = "resilience_value"
    addgvar(key, val)

    # Cached read should succeed
    assert gvarstatus(key) == val

    # Simulate database query failure on next call
    with patch("userbot.sql_helper.globals.SESSION.query") as mock_query:
        mock_query.side_effect = OperationalError("connection lost", {}, None)
        # Because value is cached with TTL, it is served safely without hitting failed DB
        assert gvarstatus(key) == val

    # Clean up
    delgvar(key)


def test_database_transaction_rollback_on_failure():
    """Verify that a failed write triggers transaction rollback."""
    from userbot.sql_helper.globals import Globals, SESSION

    with patch.object(SESSION, "commit", side_effect=Exception("Disk full")):
        with patch.object(SESSION, "rollback") as mock_rollback:
            with pytest.raises(Exception, match="Disk full"):
                addgvar("fail_key", "fail_val")
            mock_rollback.assert_called_once()


def test_database_connection_check():
    """Verify check_connection returns True for active DB and handles errors."""
    assert check_connection() is True
