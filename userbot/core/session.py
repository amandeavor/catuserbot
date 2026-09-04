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

if Config.STRING_SESSION:
    session = StringSession(str(Config.STRING_SESSION))
else:
    session = "catuserbot"

api_id = Config.APP_ID or 6
api_hash = Config.API_HASH or "0123456789abcdef0123456789abcdef"

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
except Exception as e:
    print(f"Notice: Initializing fallback client ({e})")
    catub = CatUserBotClient(
        session=None,
        api_id=6,
        api_hash="0123456789abcdef0123456789abcdef",
        loop=loop,
        app_version=__version__,
    )

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
    tgbot_client = CatUserBotClient(
        session=None,
        api_id=6,
        api_hash="0123456789abcdef0123456789abcdef",
        loop=loop,
        app_version=__version__,
    )

if Config.TG_BOT_TOKEN:
    try:
        tgbot_client.start(bot_token=Config.TG_BOT_TOKEN)
    except Exception as e:
        print(f"Warning: Unable to start tgbot: {e}")

catub.tgbot = tgbot = tgbot_client
