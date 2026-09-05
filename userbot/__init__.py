# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris UserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import sys
import time

try:
    import heroku3
except ImportError:
    heroku3 = None

from .Config import Config
from .core.logger import logging
from .core.session import catub
try:
    from .helpers.functions.converter import Convert
except Exception:
    Convert = None

try:
    from .helpers.functions.musictool import *
except Exception:
    pass

from .helpers.utils.utils import runasync
from .sql_helper.globals import addgvar, delgvar, gvarstatus

__version__ = "5.0.0-rc2"
__license__ = "GNU Affero General Public License v3.0"
__author__ = "Aetheris <https://github.com/amandeavor/catuserbot>"
__copyright__ = f"Copyright (C) 2026  {__author__}"

catub.version = __version__
catub.tgbot.version = __version__
LOGS = logging.getLogger("Aetheris")
bot = catub
aetheris = catub

StartTime = time.time()
catversion = "5.0.0-rc2"
aetherisversion = "5.0.0-rc2"


UPSTREAM_REPO_URL = Config.UPSTREAM_REPO

if Config.PRIVATE_GROUP_BOT_API_ID == 0:
    val = gvarstatus("PRIVATE_GROUP_BOT_API_ID")
    if val is None or not str(val).lstrip("-").isdigit():
        Config.BOTLOG = False
        Config.BOTLOG_CHATID = "me"
    else:
        Config.BOTLOG_CHATID = int(val)
        Config.PRIVATE_GROUP_BOT_API_ID = int(val)
        Config.BOTLOG = True
else:
    if str(Config.PRIVATE_GROUP_BOT_API_ID)[0] != "-":
        Config.BOTLOG_CHATID = int(f"-{str(Config.PRIVATE_GROUP_BOT_API_ID)}")
    else:
        Config.BOTLOG_CHATID = Config.PRIVATE_GROUP_BOT_API_ID
    Config.BOTLOG = True

if Config.PM_LOGGER_GROUP_ID == 0:
    pm_val = gvarstatus("PM_LOGGER_GROUP_ID")
    if pm_val is None or not str(pm_val).lstrip("-").isdigit():
        Config.PM_LOGGER_GROUP_ID = -100
    else:
        Config.PM_LOGGER_GROUP_ID = int(pm_val)
elif str(Config.PM_LOGGER_GROUP_ID)[0] != "-":
    Config.PM_LOGGER_GROUP_ID = int(f"-{str(Config.PM_LOGGER_GROUP_ID)}")

try:
    if Config.HEROKU_API_KEY is not None or Config.HEROKU_APP_NAME is not None:
        HEROKU_APP = heroku3.from_key(Config.HEROKU_API_KEY).apps()[
            Config.HEROKU_APP_NAME
        ]
    else:
        HEROKU_APP = None
except Exception:
    HEROKU_APP = None


# Global Variables
COUNT_MSG = 0
USERS = {}
COUNT_PM = {}
LASTMSG = {}
CMD_HELP = {}
ISAFK = False
AFKREASON = None
CMD_LIST = {}
SUDO_LIST = {}
# for later purposes
INT_PLUG = ""
LOAD_PLUG = {}

# Variables
BOTLOG = Config.BOTLOG
BOTLOG_CHATID = Config.BOTLOG_CHATID
PM_LOGGER_GROUP_ID = Config.PM_LOGGER_GROUP_ID
