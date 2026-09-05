# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import enum
import os
import time
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

from ..Config import Config
from ..core.logger import logging

LOGS = logging.getLogger("Aetheris.DB")
BASE = declarative_base()


class StorageMode(enum.Enum):
    SQLITE = "SQLITE"
    POSTGRESQL = "POSTGRESQL"


STORAGE_MODE: StorageMode = StorageMode.SQLITE
ENGINE = None
SESSION: Optional[scoped_session] = None


def get_storage_mode() -> str:
    """Returns the current explicit storage mode ('SQLITE' or 'POSTGRESQL')."""
    return STORAGE_MODE.value


def _resolve_storage_mode(raw_uri: Optional[str]) -> tuple[StorageMode, str]:
    if not raw_uri or raw_uri.strip().lower() in {"none", "null", "sqlite", "value", "your_value", "<value>", "undefined"}:
        return StorageMode.SQLITE, "sqlite:///aetheris.db"
    
    clean_uri = raw_uri.strip()
    if clean_uri.startswith("sqlite"):
        return StorageMode.SQLITE, clean_uri

    if clean_uri.startswith("postgres://"):
        clean_uri = clean_uri.replace("postgres://", "postgresql://", 1)

    if clean_uri.startswith(("postgresql://", "postgresql+psycopg2://")):
        return StorageMode.POSTGRESQL, clean_uri

    raise ValueError("Unsupported configured database URI; refusing to select another database.")


def start() -> scoped_session:
    global ENGINE, STORAGE_MODE, SESSION

    raw_uri = getattr(Config, "DB_URI", None)
    mode, db_uri = _resolve_storage_mode(raw_uri)
    STORAGE_MODE = mode

    connect_args = {}
    if STORAGE_MODE == StorageMode.SQLITE:
        connect_args["check_same_thread"] = False
        LOGS.info("Explicit SQLite storage mode active: %s", db_uri)
    else:
        LOGS.info("Explicit PostgreSQL storage mode configured: %s", db_uri.split("@")[-1] if "@" in db_uri else "postgresql")

    max_attempts = 1 if STORAGE_MODE == StorageMode.SQLITE else 3
    last_err = None

    for attempt in range(1, max_attempts + 1):
        candidate_engine = None
        try:
            candidate_engine = create_engine(db_uri, connect_args=connect_args)
            # Verify connectivity immediately with a ping before setting global state
            with candidate_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            ENGINE = candidate_engine
            BASE.metadata.bind = ENGINE
            BASE.metadata.create_all(ENGINE)
            SESSION = scoped_session(sessionmaker(bind=ENGINE, autoflush=False))
            return SESSION
        except Exception as exc:
            if candidate_engine is not None:
                candidate_engine.dispose()
            last_err = exc
            LOGS.warning("Database connection attempt %d/%d failed (%s)", attempt, max_attempts, type(exc).__name__)
            if attempt < max_attempts:
                time.sleep(1.0)

    # If PostgreSQL fails, DO NOT silently switch to SQLite.
    # Silent failover creates split-brain state when PostgreSQL recovers.
    if STORAGE_MODE == StorageMode.POSTGRESQL:
        err_msg = (
            f"Configured PostgreSQL database is unreachable after {max_attempts} attempts. "
            "To prevent split-brain state loss, Aetheris V5 strictly refuses to silently switch to SQLite. "
            "Verify your PostgreSQL connection or remove DB_URI to explicitly run in SQLite mode."
        )
        LOGS.critical(err_msg)
        raise RuntimeError(err_msg) from None

    # SQLite fallback error (e.g. disk permission issue)
    raise RuntimeError("Failed to initialize the configured SQLite database; persistent storage is required.") from None


def check_connection() -> bool:
    """Verifies that the database engine is healthy and accepting queries."""
    if ENGINE is None:
        return False
    try:
        with ENGINE.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def reconnect() -> bool:
    """Attempts to reconnect to the authoritative database."""
    global SESSION
    try:
        SESSION = start()
        return True
    except Exception as e:
        LOGS.error("Database reconnection failed: %s", e)
        return False


# A failed authoritative database must stop startup, including SQLite failures.
SESSION = start()
