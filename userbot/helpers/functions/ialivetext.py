# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris UserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import math
import time

import heroku3
import requests

from ...Config import Config
from .utils import get_readable_time

Heroku = heroku3.from_key(Config.HEROKU_API_KEY) if Config.HEROKU_API_KEY else None
heroku_api = "https://api.heroku.com"


def check_data_base_heal_th():
    is_database_working = False
    output = "No Database set"
    if not Config.DB_URI:
        return is_database_working, output
    from ...sql_helper import SESSION

    try:
        SESSION.execute("SELECT 1")
    except Exception as e:
        output = f"Offline ({e})"
        is_database_working = False
    else:
        output = "Operational"
        is_database_working = True
    return is_database_working, output


async def catalive(StartTime):
    _, check_sgnirts = check_data_base_heal_th()
    sudo = "Enabled" if Config.SUDO_USERS else "Disabled"
    uptime = await get_readable_time((time.time() - StartTime))
    dyno = "VPS / Localhost"
    if Config.HEROKU_API_KEY and Heroku:
        try:
            useragent = (
                "Mozilla/5.0 (Linux; Android 10; SM-G975F) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/80.0.3987.149 Mobile Safari/537.36"
            )
            user_id = Heroku.account().id
            headers = {
                "User-Agent": useragent,
                "Authorization": f"Bearer {Config.HEROKU_API_KEY}",
                "Accept": "application/vnd.heroku+json; version=3.account-quotas",
            }
            path = f"/accounts/{user_id}/actions/get-quota"
            r = requests.get(heroku_api + path, headers=headers, timeout=5)
            result = r.json()
            quota = result["account_quota"]
            quota_used = result["quota_used"]

            remaining_quota = quota - quota_used
            minutes_remaining = remaining_quota / 60
            hours = math.floor(minutes_remaining / 60)
            minutes = math.floor(minutes_remaining % 60)

            App = result["apps"]
            try:
                AppQuotaUsed = App[0]["quota_used"] / 60
            except (IndexError, KeyError):
                AppQuotaUsed = 0
            AppHours = math.floor(AppQuotaUsed / 60)
            AppMinutes = math.floor(AppQuotaUsed % 60)
            dyno = f"{AppHours}h {AppMinutes}m / {hours}h {minutes}m"
        except Exception:
            dyno = "Heroku Connected"

    return f"◈ ─── **A E T H E R I S  S T A T S** ─── ◈\
                 \n\n▸ **Database :** {check_sgnirts}\
                  \n▸ **Sudo     :** {sudo}\
                  \n▸ **Uptime   :** {uptime}\
                  \n▸ **Host/Dyn :** {dyno}\
                  \n◈ ──────────────────────────── ◈"
