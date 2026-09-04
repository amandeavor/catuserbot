# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris UserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import platform
import sys
from datetime import datetime

import psutil
from telethon import __version__

from userbot import catub, catversion

from ..core.managers import edit_or_reply
from ..helpers.utils import _catutils

plugin_category = "tools"


def get_size(inputbytes, suffix="B"):
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if inputbytes < factor:
            return f"{inputbytes:.2f}{unit}{suffix}"
        inputbytes /= factor


@catub.cat_cmd(
    pattern="(?:spc|sysinfo)$",
    command=("spc", plugin_category),
    info={
        "header": "To show full hardware and system specifications.",
        "usage": "{tr}spc or {tr}sysinfo",
    },
)
async def psu(event):
    "shows system specification"
    uname = platform.uname()
    boot_time_timestamp = psutil.boot_time()
    bt = datetime.fromtimestamp(boot_time_timestamp)
    boot_str = bt.strftime("%Y-%m-%d %H:%M:%S")

    # CPU
    physical_cores = psutil.cpu_count(logical=False) or 1
    total_cores = psutil.cpu_count(logical=True) or 1
    cpufreq = psutil.cpu_freq()
    freq_str = f"{cpufreq.current:.1f} MHz" if cpufreq else "Standard"
    cpu_percent = psutil.cpu_percent(interval=None)

    # RAM
    svmem = psutil.virtual_memory()
    ram_used = get_size(svmem.used)
    ram_total = get_size(svmem.total)
    ram_percent = svmem.percent

    # Bandwidth
    net = psutil.net_io_counters()
    net_up = get_size(net.bytes_sent)
    net_down = get_size(net.bytes_recv)

    # Disk
    disk = psutil.disk_usage('/')
    disk_used = get_size(disk.used)
    disk_total = get_size(disk.total)
    disk_percent = disk.percent

    out = f"""◈ ─── ❖ **[ A E T H E R I S  S Y S T E M ]** ❖ ─── ◈
▸ **Platform    :** `{uname.system} {uname.release} ({uname.machine})`
▸ **Boot Time   :** `{boot_str}`

▸ **CPU Cores   :** `{physical_cores} Physical / {total_cores} Logical`
▸ **CPU Clock   :** `{freq_str}`
▸ **CPU Load    :** `{cpu_percent}%`

▸ **Memory      :** `{ram_used} / {ram_total} ({ram_percent}%)`
▸ **Storage     :** `{disk_used} / {disk_total} ({disk_percent}%)`
▸ **Bandwidth   :** `▲ {net_up} | ▼ {net_down}`

▸ **Engine      :** `Aetheris v{catversion}`
▸ **Telethon    :** `v{__version__}`
▸ **Python      :** `v{sys.version.split()[0]}`
◈ ───────────────────────────────────── ◈"""
    await edit_or_reply(event, out)


@catub.cat_cmd(
    pattern="cpu$",
    command=("cpu", plugin_category),
    info={
        "header": "To show cpu model information.",
        "usage": "{tr}cpu",
    },
)
async def cpu(event):
    "shows cpu information"
    cmd = "cat /proc/cpuinfo | grep 'model name' | head -n 1"
    o = (await _catutils.runcmd(cmd))[0].strip()
    if not o:
        o = platform.processor() or "Modern Host Processor"
    else:
        o = o.split(":", 1)[-1].strip()
    await edit_or_reply(
        event, f"◈ ─── **A E T H E R I S  C P U** ─── ◈\n▸ **Model :** `{o}`\n◈ ──────────────────────────── ◈"
    )


@catub.cat_cmd(
    pattern="sysd$",
    command=("sysd", plugin_category),
    info={
        "header": "Shows system information using neofetch",
        "usage": "{tr}sysd",
    },
)
async def sysdetails(sysd):
    "Shows system information using neofetch"
    catevent = await edit_or_reply(sysd, "◈ `Fetching Neofetch system diagnostics...`")
    cmd = "git clone https://github.com/dylanaraps/neofetch.git"
    await _catutils.runcmd(cmd)
    neo = "neofetch/neofetch --off --color_blocks off --bold off --cpu_temp C \
                    --cpu_speed on --cpu_cores physical --kernel_shorthand off --stdout"
    a, b, c, d = await _catutils.runcmd(neo)
    result = str(a) + str(b)
    await edit_or_reply(catevent, f"◈ ─── **A E T H E R I S  N E O F E T C H** ─── ◈\n`{result}`")
