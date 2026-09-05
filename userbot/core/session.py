# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.

# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement".

# Please see: https://github.com/TgCatUB/catuserbot/blob/master/LICENSE
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import sys

from telethon.network.connection.tcpabridged import ConnectionTcpAbridged
from telethon.sessions import StringSession

from ..Config import Config
from .client import CatUserBotClient

__version__ = "3.3.0"

loop = None

raw_session = Config.STRING_SESSION
if raw_session:
    try:
        session = StringSession(str(raw_session).strip())
        if session.auth_key is None:
            raise ValueError("No authorization key")
    except Exception:
        raise ValueError("Invalid STRING_SESSION; refusing to select another session store.") from None
else:
    session = "catuserbot"

api_id = Config.APP_ID
api_hash = Config.API_HASH
if not api_id or not api_hash:
    raise ValueError("APP_ID and API_HASH are required; no substitute credentials will be used.")

try:
    catub = CatUserBotClient(
        session=session,
        api_id=api_id,
        api_hash=api_hash,
        loop=loop,
        app_version=__version__,
        connection=ConnectionTcpAbridged,
        auto_reconnect=True,
        connection_retries=None,
    )
except Exception:
    raise RuntimeError("Cannot open the configured user session; existing authorization was not replaced.") from None

try:
    tgbot_client = CatUserBotClient(
        session="CatTgbot",
        api_id=api_id,
        api_hash=api_hash,
        loop=loop,
        app_version=__version__,
        connection=ConnectionTcpAbridged,
        auto_reconnect=True,
        connection_retries=None,
    )
except Exception:
    raise RuntimeError("Cannot open the assistant session; existing authorization was not replaced.") from None

catub.tgbot = tgbot = tgbot_client
