# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

from ..Config import Config
from ..core.logger import logging

LOGS = logging.getLogger("Aetheris.DB")
BASE = declarative_base()


ENGINE = None


def start() -> scoped_session:
    global ENGINE
    db_uri = getattr(Config, "DB_URI", None)
    if not db_uri or db_uri.strip().lower() in {"none", "null", "sqlite"}:
        db_uri = "sqlite:///aetheris.db"
        LOGS.info("No external PostgreSQL DB_URI found; using resilient local SQLite storage: %s", db_uri)
    elif "postgres://" in db_uri:
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)

    connect_args = {}
    if db_uri.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    ENGINE = create_engine(db_uri, connect_args=connect_args)
    BASE.metadata.bind = ENGINE
    BASE.metadata.create_all(ENGINE)
    return scoped_session(sessionmaker(bind=ENGINE, autoflush=False))


try:
    SESSION = start()
except Exception as e:
    LOGS.error("Error initializing primary database: %s. Falling back to local SQLite.", e)
    ENGINE = create_engine("sqlite:///aetheris.db", connect_args={"check_same_thread": False})
    BASE.metadata.bind = ENGINE
    BASE.metadata.create_all(ENGINE)
    SESSION = scoped_session(sessionmaker(bind=ENGINE, autoflush=False))
