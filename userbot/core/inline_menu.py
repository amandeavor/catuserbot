# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import math
import platform
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import telethon
from telethon import Button
from telethon.errors import MessageIdInvalidError, MessageNotModifiedError

from ..Config import Config
from ..sql_helper.globals import addgvar, delgvar, gvarstatus
from . import CMD_INFO, GRP_INFO, PLG_INFO
from .callbacks import CallbackToken, secure_callbacks
from .cmdinfo import get_key, getkey
from .jobs.supervisor import JobState, job_supervisor
from .logger import logging
from .tasks import task_manager

LOG = logging.getLogger("Aetheris.InlineMenu")

CATEGORY_ICONS: Dict[str, str] = {
    "admin": "👮",
    "bot": "🤖",
    "fun": "🎨",
    "misc": "🧩",
    "tools": "🧰",
    "utils": "🗂",
    "extra": "➕",
    "useless": "⚰️",
}

_START_TIME = time.time()


def get_allowed_users(sender_id: Optional[int] = None) -> Set[int]:
    """Resolve set of user IDs permitted to interact with privileged menus."""
    allowed: Set[int] = set()
    if Config.OWNER_ID:
        try:
            allowed.add(int(Config.OWNER_ID))
        except (ValueError, TypeError):
            pass
    if Config.SUDO_USERS:
        for u in Config.SUDO_USERS:
            try:
                allowed.add(int(u))
            except (ValueError, TypeError):
                pass
    if sender_id is not None:
        try:
            allowed.add(int(sender_id))
        except (ValueError, TypeError):
            pass
    return allowed


def create_menu_token(
    action: str,
    payload: Optional[Dict[str, Any]] = None,
    sender_id: Optional[int] = None,
    ttl: float = 900.0,
    single_use: bool = False,
) -> str:
    """Convenience wrapper to create an opaque, authorized callback token."""
    allowed = get_allowed_users(sender_id)
    return secure_callbacks.create_token(
        action=action,
        payload=payload or {},
        allowed_user_ids=allowed,
        ttl=ttl,
        single_use=single_use,
    )


_message_revisions: Dict[str, int] = {}
_revisions_lock = asyncio.Lock()


def get_message_key(event: Any) -> str:
    """Extract unique identifier for message, handling inline_message_id and chat:msg pairs."""
    inline_id = getattr(event, "inline_message_id", None)
    if inline_id:
        return f"inline:{inline_id}"
    chat_id = getattr(event, "chat_id", None)
    msg_id = getattr(event, "message_id", None)
    return f"{chat_id}:{msg_id}"


async def acquire_message_revision(event: Any) -> int:
    """Atomically advance and acquire the latest revision number for a menu message."""
    key = get_message_key(event)
    async with _revisions_lock:
        rev = _message_revisions.get(key, 0) + 1
        _message_revisions[key] = rev
        if len(_message_revisions) > 1000:
            for k in list(_message_revisions.keys())[:-500]:
                _message_revisions.pop(k, None)
        return rev


async def is_latest_message_revision(event: Any, rev: int) -> bool:
    """Check if the acquired revision is still the newest for this message."""
    key = get_message_key(event)
    async with _revisions_lock:
        return _message_revisions.get(key, 0) == rev


async def safe_edit(
    event: Any,
    text: str,
    buttons: Any = None,
    parse_mode: str = "md",
    rev: Optional[int] = None,
) -> bool:
    """Safely edit message while checking revision to avoid older navigation overwriting newer."""
    if rev is not None:
        if not await is_latest_message_revision(event, rev):
            LOG.debug("Skipping superseded edit for message %s (rev %d)", get_message_key(event), rev)
            return False

    try:
        await event.edit(text, buttons=buttons, parse_mode=parse_mode)
        return True
    except (MessageNotModifiedError, MessageIdInvalidError):
        return True
    except Exception as e:
        LOG.warning("Failed to edit menu message: %s", e)
        return False


def get_uptime_str() -> str:
    """Return formatted system uptime."""
    delta = int(time.time() - _START_TIME)
    days, remainder = divmod(delta, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def get_active_tasks_count() -> int:
    """Count currently running tasks across task_manager and job_supervisor."""
    tm_tasks = len(task_manager.list_active_tasks())
    js_jobs = len(job_supervisor.list_jobs(active_only=True))
    return tm_tasks + js_jobs


# ---------------------------------------------------------------------------
# View 1: Home Menu
# ---------------------------------------------------------------------------

def build_home_menu(sender_id: Optional[int] = None) -> Tuple[str, List[List[Button]]]:
    """Generate the Home / Status dashboard view."""
    cmdprefix = Config.COMMAND_HAND_LER or "."
    owner_id = Config.OWNER_ID or "Master"
    active_tasks = get_active_tasks_count()

    text = (
        "**◈ AETHERIS CONTROL ◈**\n"
        f"`v5.0.0-rc2` • `Operational`\n\n"
        f"• **Prefix:** `{cmdprefix}` • **Owner ID:** `{owner_id}`\n"
        f"• **Modules:** `{len(PLG_INFO)}` plugins (`{len(CMD_INFO)}` commands)\n"
        f"• **Active Tasks:** `{active_tasks}` running\n"
        f"• **Uptime:** `{get_uptime_str()}`\n\n"
        "Select a section below to browse commands, configure settings, or inspect background tasks:"
    )

    t_cmds = create_menu_token("menu_categories", {"sender_id": sender_id}, sender_id)
    t_settings = create_menu_token("menu_settings", {"sender_id": sender_id}, sender_id)
    t_tasks = create_menu_token("menu_tasks", {"sender_id": sender_id}, sender_id)
    t_info = create_menu_token("menu_sysinfo", {"sender_id": sender_id}, sender_id)
    t_close = create_menu_token("menu_close", {"sender_id": sender_id}, sender_id)

    buttons = [
        [
            Button.inline("📚 Commands", data=t_cmds),
            Button.inline("⚙️ Settings", data=t_settings),
        ],
        [
            Button.inline(f"⚡ Tasks ({active_tasks})", data=t_tasks),
            Button.switch_inline("🔎 Quick Search", query="s ", same_peer=True),
        ],
        [
            Button.inline("ℹ️ System Info", data=t_info),
            Button.inline("🔒 Close", data=t_close),
        ],
    ]
    return text, buttons


# ---------------------------------------------------------------------------
# View 2: Categories Overview
# ---------------------------------------------------------------------------

def build_categories_menu(sender_id: Optional[int] = None) -> Tuple[str, List[List[Button]]]:
    """Generate the command category overview."""
    categories = ["admin", "bot", "fun", "misc", "tools", "utils", "extra"]
    if getattr(Config, "BADCAT", False):
        categories.append("useless")

    text = (
        "**◈ COMMAND CATEGORIES ◈**\n"
        f"Total: `{len(PLG_INFO)}` plugins registered across `{len(categories)}` categories.\n\n"
        "Select a category to view its modules:"
    )

    cat_buttons = []
    row = []
    for cat in categories:
        plugins = GRP_INFO.get(cat, [])
        icon = CATEGORY_ICONS.get(cat, "📁")
        tok = create_menu_token(
            "menu_category", {"category": cat, "page": 0, "sender_id": sender_id}, sender_id
        )
        row.append(Button.inline(f"{icon} {cat.capitalize()} ({len(plugins)})", data=tok))
        if len(row) == 2:
            cat_buttons.append(row)
            row = []
    if row:
        cat_buttons.append(row)

    t_home = create_menu_token("menu_home", {"sender_id": sender_id}, sender_id)
    cat_buttons.append([
        Button.switch_inline("🔎 Search", query="s ", same_peer=True),
        Button.inline("🏠 Home", data=t_home),
    ])

    return text, cat_buttons


# ---------------------------------------------------------------------------
# View 3: Category Plugins Browser (Paginated)
# ---------------------------------------------------------------------------

def build_category_plugins_menu(
    category: str,
    page: int = 0,
    sender_id: Optional[int] = None,
) -> Tuple[str, List[List[Button]]]:
    """Generate the plugins list within a specific category with bounded pagination."""
    plugins = sorted(GRP_INFO.get(category, []))
    total_plugins = len(plugins)

    try:
        page_size = int(gvarstatus("NO_OF_ROWS_IN_HELP") or 6)
        if page_size < 2 or page_size > 14:
            page_size = 6
    except (ValueError, TypeError):
        page_size = 6

    # 2 columns per row
    per_page = page_size * 2
    total_pages = max(1, math.ceil(total_plugins / per_page)) if total_plugins > 0 else 1

    # Boundary clamp
    page = max(0, min(page, total_pages - 1))

    start_idx = page * per_page
    page_plugins = plugins[start_idx : start_idx + per_page]

    total_cmds = sum(len(PLG_INFO.get(p, [])) for p in plugins)
    icon = CATEGORY_ICONS.get(category, "📁")

    text = (
        f"**◈ CATEGORY: {icon} {category.upper()} ◈**\n"
        f"Plugins: `{total_plugins}` • Commands: `{total_cmds}`\n"
        f"Page {page + 1} of {total_pages}\n\n"
        "Select a module to view its available commands:"
    )

    buttons = []
    row = []
    for plg in page_plugins:
        cmd_count = len(PLG_INFO.get(plg, []))
        tok = create_menu_token(
            "menu_plugin",
            {
                "plugin": plg,
                "category": category,
                "cat_page": page,
                "page": 0,
                "sender_id": sender_id,
            },
            sender_id,
        )
        row.append(Button.inline(f"{plg} ({cmd_count})", data=tok))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Pagination controls
    if total_pages > 1:
        prev_page = max(0, page - 1)
        next_page = min(total_pages - 1, page + 1)
        t_prev = create_menu_token(
            "menu_category", {"category": category, "page": prev_page, "sender_id": sender_id}, sender_id
        )
        t_noop = create_menu_token("noop", {"sender_id": sender_id}, sender_id)
        t_next = create_menu_token(
            "menu_category", {"category": category, "page": next_page, "sender_id": sender_id}, sender_id
        )
        buttons.append([
            Button.inline("« Prev", data=t_prev),
            Button.inline(f"{page + 1}/{total_pages}", data=t_noop),
            Button.inline("Next »", data=t_next),
        ])

    t_cats = create_menu_token("menu_categories", {"sender_id": sender_id}, sender_id)
    t_home = create_menu_token("menu_home", {"sender_id": sender_id}, sender_id)
    buttons.append([
        Button.inline("⬅️ Categories", data=t_cats),
        Button.inline("🏠 Home", data=t_home),
    ])

    return text, buttons


# ---------------------------------------------------------------------------
# View 4: Plugin Commands Browser
# ---------------------------------------------------------------------------

def build_plugin_commands_menu(
    plugin: str,
    category: str,
    cat_page: int = 0,
    page: int = 0,
    sender_id: Optional[int] = None,
) -> Tuple[str, List[List[Button]]]:
    """Generate the commands list for a chosen plugin."""
    cmdprefix = Config.COMMAND_HAND_LER or "."
    commands = sorted(PLG_INFO.get(plugin, []))
    total_cmds = len(commands)

    per_page = 8
    total_pages = max(1, math.ceil(total_cmds / per_page)) if total_cmds > 0 else 1
    page = max(0, min(page, total_pages - 1))

    start_idx = page * per_page
    page_cmds = commands[start_idx : start_idx + per_page]

    text = (
        f"**◈ PLUGIN: `{plugin.upper()}` ◈**\n"
        f"Category: `{category.capitalize()}` • Commands: `{total_cmds}`\n"
    )
    if total_pages > 1:
        text += f"Page `{page + 1}` of `{total_pages}`\n"
    text += "\nSelect a command to view detailed syntax and options:"

    buttons = []
    row = []
    for cmd in page_cmds:
        tok = create_menu_token(
            "menu_command",
            {
                "cmd": cmd,
                "plugin": plugin,
                "category": category,
                "cat_page": cat_page,
                "plg_page": page,
                "sender_id": sender_id,
            },
            sender_id,
        )
        row.append(Button.inline(f"{cmdprefix}{cmd}", data=tok))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    if total_pages > 1:
        prev_p = max(0, page - 1)
        next_p = min(total_pages - 1, page + 1)
        t_prev = create_menu_token(
            "menu_plugin",
            {
                "plugin": plugin,
                "category": category,
                "cat_page": cat_page,
                "page": prev_p,
                "sender_id": sender_id,
            },
            sender_id,
        )
        t_noop = create_menu_token("noop", {"sender_id": sender_id}, sender_id)
        t_next = create_menu_token(
            "menu_plugin",
            {
                "plugin": plugin,
                "category": category,
                "cat_page": cat_page,
                "page": next_p,
                "sender_id": sender_id,
            },
            sender_id,
        )
        buttons.append([
            Button.inline("« Prev", data=t_prev),
            Button.inline(f"{page + 1}/{total_pages}", data=t_noop),
            Button.inline("Next »", data=t_next),
        ])

    t_back_cat = create_menu_token(
        "menu_category", {"category": category, "page": cat_page, "sender_id": sender_id}, sender_id
    )
    t_home = create_menu_token("menu_home", {"sender_id": sender_id}, sender_id)
    buttons.append([
        Button.inline(f"⬅️ {category.capitalize()}", data=t_back_cat),
        Button.inline("🏠 Home", data=t_home),
    ])

    return text, buttons


# ---------------------------------------------------------------------------
# View 5: Command Details View
# ---------------------------------------------------------------------------

def get_command_permission(cmd: str) -> str:
    """
    Derive execution permissions from the authoritative registration and execution path:
    atomic_registry, client.py registration metadata, and active sudo configuration.
    """
    try:
        from .plugins.registry import atomic_registry
        handler_id = atomic_registry._command_map.get(cmd.lower())
        handler = atomic_registry._handlers.get(handler_id) if handler_id else None
    except Exception:
        handler = None

    scopes = []
    if handler:
        if handler.groups_only:
            scopes.append("Groups Only")
        elif handler.private_only:
            scopes.append("Direct Messages Only")

        if not handler.allow_sudo:
            auth = "Master Only"
        elif gvarstatus("sudoenable") is not None and Config.SUDO_USERS:
            auth = "Master & Authorized Sudo"
        else:
            auth = "Master Only"
    else:
        if gvarstatus("sudoenable") is not None and Config.SUDO_USERS:
            auth = "Master & Authorized Sudo"
        else:
            auth = "Master Only"

    if scopes:
        return f"{auth} ({', '.join(scopes)})"
    return auth


def build_command_details_menu(
    cmd: str,
    plugin: str,
    category: str,
    cat_page: int = 0,
    plg_page: int = 0,
    sender_id: Optional[int] = None,
) -> Tuple[str, List[List[Button]]]:
    """Generate detailed command guidance derived from authoritative CMD_INFO metadata."""
    cmdprefix = Config.COMMAND_HAND_LER or "."
    info = CMD_INFO.get(cmd)

    doc_summary = "No description provided."
    body_text = ""
    if info:
        if len(info) > 0 and info[0]:
            body_text = str(info[0]).replace("{tr}", cmdprefix)
        if len(info) > 1 and info[1]:
            doc_summary = str(info[1]).strip()

    perm = get_command_permission(cmd)

    text = (
        f"**◈ COMMAND: `{cmdprefix}{cmd}` ◈**\n"
        f"• **Plugin:** `{plugin}`\n"
        f"• **Category:** `{category.capitalize()}`\n"
        f"• **Permissions:** `{perm}`\n"
        f"• **Summary:** {doc_summary}\n\n"
    )

    if body_text:
        text += f"**Details & Syntax:**\n{body_text}\n"
    else:
        text += f"**Syntax:** `{cmdprefix}{cmd}`\n"

    t_back_plg = create_menu_token(
        "menu_plugin",
        {
            "plugin": plugin,
            "category": category,
            "cat_page": cat_page,
            "page": plg_page,
            "sender_id": sender_id,
        },
        sender_id,
    )
    t_cats = create_menu_token("menu_categories", {"sender_id": sender_id}, sender_id)
    t_home = create_menu_token("menu_home", {"sender_id": sender_id}, sender_id)

    buttons = [
        [Button.inline(f"⬅️ Back to {plugin}", data=t_back_plg)],
        [
            Button.inline("📚 Categories", data=t_cats),
            Button.inline("🏠 Home", data=t_home),
        ],
    ]

    return text, buttons


# ---------------------------------------------------------------------------
# View 6: Settings Dashboard
# ---------------------------------------------------------------------------

def build_settings_menu(sender_id: Optional[int] = None) -> Tuple[str, List[List[Button]]]:
    """Generate the interactive settings control panel."""
    # Retrieve current genuine values
    allow_nsfw_raw = gvarstatus("ALLOW_NSFW")
    allow_nsfw = bool(allow_nsfw_raw and str(allow_nsfw_raw).lower() in {"true", "yes", "1"})

    spoiler_raw = gvarstatus("SPOILER_MEDIA")
    spoiler_media = bool(spoiler_raw and str(spoiler_raw).lower() in {"true", "yes", "1"})

    pmpermit_raw = gvarstatus("pmpermit")
    pmpermit = bool(pmpermit_raw is not None)

    bot_antif_raw = gvarstatus("bot_antif")
    bot_antif = bool(bot_antif_raw is not None)

    try:
        help_rows = int(gvarstatus("NO_OF_ROWS_IN_HELP") or 5)
    except (ValueError, TypeError):
        help_rows = 5

    text = (
        "**◈ SYSTEM SETTINGS ◈**\n"
        "Configure runtime database toggles for Aetheris:\n\n"
        f"• **ALLOW_NSFW:** `{'Enabled 🟢' if allow_nsfw else 'Disabled ⚪'}`\n"
        "  Controls execution permission for adult/NSFW commands.\n\n"
        f"• **SPOILER_MEDIA:** `{'Enabled 🟢' if spoiler_media else 'Disabled ⚪'}`\n"
        "  Automatically flags outgoing media uploads as spoilers.\n\n"
        f"• **PM_GUARD:** `{'Enabled 🟢' if pmpermit else 'Disabled ⚪'}`\n"
        "  Enforces automatic direct-message permission guard (pmpermit).\n\n"
        f"• **BOT_ANTIFLOOD:** `{'Active 🟢' if bot_antif else 'Disabled ⚪'}`\n"
        "  Assistant bot direct-message flood rate limiter.\n\n"
        f"• **HELP_ROWS:** `{help_rows}` rows\n"
        "  Controls vertical density in paginated menus.\n\n"
        "Tap a button to toggle a setting:"
    )

    t_nsfw = create_menu_token(
        "setting_toggle",
        {"key": "ALLOW_NSFW", "current": allow_nsfw, "sender_id": sender_id},
        sender_id,
        single_use=True,
    )
    t_spoiler = create_menu_token(
        "setting_toggle",
        {"key": "SPOILER_MEDIA", "current": spoiler_media, "sender_id": sender_id},
        sender_id,
        single_use=True,
    )
    t_pmpermit = create_menu_token(
        "setting_toggle",
        {"key": "pmpermit", "current": pmpermit, "sender_id": sender_id},
        sender_id,
        single_use=True,
    )
    t_antif = create_menu_token(
        "setting_toggle",
        {"key": "bot_antif", "current": bot_antif, "sender_id": sender_id},
        sender_id,
        single_use=True,
    )
    t_rows = create_menu_token(
        "setting_cycle_rows",
        {"current": help_rows, "sender_id": sender_id},
        sender_id,
        single_use=True,
    )
    t_refresh = create_menu_token("menu_settings", {"sender_id": sender_id}, sender_id)
    t_home = create_menu_token("menu_home", {"sender_id": sender_id}, sender_id)
    t_close = create_menu_token("menu_close", {"sender_id": sender_id}, sender_id)

    buttons = [
        [
            Button.inline(f"NSFW: {'🟢 ON' if allow_nsfw else '⚪ OFF'}", data=t_nsfw),
            Button.inline(f"Spoiler: {'🟢 ON' if spoiler_media else '⚪ OFF'}", data=t_spoiler),
        ],
        [
            Button.inline(f"PM Guard: {'🟢 ON' if pmpermit else '⚪ OFF'}", data=t_pmpermit),
            Button.inline(f"AntiFlood: {'🟢 ON' if bot_antif else '⚪ OFF'}", data=t_antif),
        ],
        [
            Button.inline(f"Help Rows: {help_rows} ⏭", data=t_rows),
            Button.inline("🔄 Refresh", data=t_refresh),
        ],
        [
            Button.inline("🏠 Home", data=t_home),
            Button.inline("🔒 Close", data=t_close),
        ],
    ]

    return text, buttons


# ---------------------------------------------------------------------------
# View 7: Active Task Controls & Safe Termination
# ---------------------------------------------------------------------------

def build_tasks_menu(sender_id: Optional[int] = None) -> Tuple[str, List[List[Button]]]:
    """Generate the active background task management interface."""
    tm_tasks = task_manager.list_active_tasks()
    js_jobs = job_supervisor.list_jobs(active_only=True)

    total_active = len(tm_tasks) + len(js_jobs)

    if total_active == 0:
        text = (
            "**◈ ACTIVE TASKS ◈**\n\n"
            "No background async tasks or jobs are currently running.\n"
            "All background workers are idle."
        )
        t_refresh = create_menu_token("menu_tasks", {"sender_id": sender_id}, sender_id)
        t_home = create_menu_token("menu_home", {"sender_id": sender_id}, sender_id)
        buttons = [
            [
                Button.inline("🔄 Refresh", data=t_refresh),
                Button.inline("🏠 Home", data=t_home),
            ]
        ]
        return text, buttons

    text = (
        "**◈ ACTIVE TASKS ◈**\n"
        f"Active background operations: `{total_active}`\n\n"
    )

    buttons = []
    # 1. AsyncTasks from task_manager
    for t in tm_tasks:
        text += (
            f"• **Task `#{t.id}`** | `{t.name}`\n"
            f"  Runtime: `{t.duration:.1f}s`"
        )
        if t.description:
            text += f" • {t.description}"
        text += "\n\n"
        tok = create_menu_token(
            "task_prompt_cancel",
            {"source": "tm", "task_id": t.id, "name": t.name, "duration": t.duration, "sender_id": sender_id},
            sender_id,
        )
        buttons.append([Button.inline(f"⏹ Cancel Task #{t.id} ({t.name[:12]})", data=tok)])

    # 2. Structured jobs from job_supervisor
    for j in js_jobs:
        run_sec = (time.time() - (j.started_at or j.created_at)) if j.started_at else 0.0
        text += (
            f"• **Job `{j.job_id}`** | `{j.name}`\n"
            f"  Status: `{j.status.value}` • Runtime: `{run_sec:.1f}s`\n\n"
        )
        tok = create_menu_token(
            "task_prompt_cancel",
            {"source": "js", "job_id": j.job_id, "name": j.name, "duration": run_sec, "sender_id": sender_id},
            sender_id,
        )
        buttons.append([Button.inline(f"⏹ Cancel Job {j.job_id} ({j.name[:12]})", data=tok)])

    t_refresh = create_menu_token("menu_tasks", {"sender_id": sender_id}, sender_id)
    t_home = create_menu_token("menu_home", {"sender_id": sender_id}, sender_id)
    buttons.append([
        Button.inline("🔄 Refresh", data=t_refresh),
        Button.inline("🏠 Home", data=t_home),
    ])

    return text, buttons


def build_task_cancel_confirmation_menu(
    payload: Dict[str, Any],
    sender_id: Optional[int] = None,
) -> Tuple[str, List[List[Button]]]:
    """Generate explicit scope-specific confirmation dialogue before task termination."""
    source = payload.get("source", "tm")
    target_id = payload.get("task_id") if source == "tm" else payload.get("job_id")
    name = payload.get("name", "Unknown")
    duration = float(payload.get("duration", 0.0))

    type_label = f"AsyncTask #{target_id}" if source == "tm" else f"Job `{target_id}`"
    text = (
        "⚠️ **CONFIRM TASK TERMINATION**\n\n"
        f"Are you sure you want to stop {type_label} (`{name}`)?\n"
        f"Runtime elapsed: `{duration:.1f}s`\n\n"
        "This will cooperatively signal cancellation and terminate execution."
    )

    confirm_tok = create_menu_token(
        "task_confirm_cancel",
        {"source": source, "target_id": target_id, "name": name, "sender_id": sender_id},
        sender_id,
        single_use=True,
    )
    cancel_tok = create_menu_token("menu_tasks", {"sender_id": sender_id}, sender_id)

    buttons = [
        [
            Button.inline("✅ Yes, Terminate", data=confirm_tok),
            Button.inline("❌ No, Keep Running", data=cancel_tok),
        ]
    ]
    return text, buttons


# ---------------------------------------------------------------------------
# View 8: System Info
# ---------------------------------------------------------------------------

def build_sysinfo_menu(sender_id: Optional[int] = None) -> Tuple[str, List[List[Button]]]:
    """Generate the system telemetry view."""
    try:
        from ..sql_helper import get_storage_mode
        storage_mode = get_storage_mode()
    except Exception:
        storage_mode = "SQLite (Local)"

    active_tasks = get_active_tasks_count()
    text = (
        "**◈ AETHERIS SYSTEM INFO ◈**\n\n"
        "• **Release:** `Aetheris V5.0.0-rc2`\n"
        f"• **Python:** `{platform.python_version()}` (`{platform.system()} {platform.release()}`)\n"
        f"• **Telethon:** `{telethon.__version__}`\n"
        f"• **Storage:** `{storage_mode}`\n"
        f"• **Uptime:** `{get_uptime_str()}`\n"
        f"• **Loaded Plugins:** `{len(PLG_INFO)}` modules\n"
        f"• **Registered Commands:** `{len(CMD_INFO)}`\n"
        f"• **Active Tasks:** `{active_tasks}` running\n"
    )

    t_home = create_menu_token("menu_home", {"sender_id": sender_id}, sender_id)
    t_close = create_menu_token("menu_close", {"sender_id": sender_id}, sender_id)

    buttons = [
        [
            Button.inline("🏠 Home", data=t_home),
            Button.inline("🔒 Close", data=t_close),
        ]
    ]
    return text, buttons


# ---------------------------------------------------------------------------
# Action Handlers Registration
# ---------------------------------------------------------------------------

async def handle_menu_home(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    sender_id = token.payload.get("sender_id")
    text, buttons = build_home_menu(sender_id)
    await safe_edit(event, text, buttons=buttons, rev=rev)
    try:
        await event.answer()
    except Exception:
        pass


async def handle_menu_categories(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    sender_id = token.payload.get("sender_id")
    text, buttons = build_categories_menu(sender_id)
    await safe_edit(event, text, buttons=buttons, rev=rev)
    try:
        await event.answer()
    except Exception:
        pass


async def handle_menu_category(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    category = token.payload.get("category", "admin")
    page = int(token.payload.get("page", 0))
    sender_id = token.payload.get("sender_id")
    text, buttons = build_category_plugins_menu(category, page, sender_id)
    await safe_edit(event, text, buttons=buttons, rev=rev)
    try:
        await event.answer()
    except Exception:
        pass


async def handle_menu_plugin(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    plugin = token.payload.get("plugin", "")
    category = token.payload.get("category", "tools")
    cat_page = int(token.payload.get("cat_page", 0))
    page = int(token.payload.get("page", 0))
    sender_id = token.payload.get("sender_id")
    text, buttons = build_plugin_commands_menu(plugin, category, cat_page, page, sender_id)
    await safe_edit(event, text, buttons=buttons, rev=rev)
    try:
        await event.answer()
    except Exception:
        pass


async def handle_menu_command(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    cmd = token.payload.get("cmd", "")
    plugin = token.payload.get("plugin", "")
    category = token.payload.get("category", "tools")
    cat_page = int(token.payload.get("cat_page", 0))
    plg_page = int(token.payload.get("plg_page", 0))
    sender_id = token.payload.get("sender_id")
    text, buttons = build_command_details_menu(cmd, plugin, category, cat_page, plg_page, sender_id)
    await safe_edit(event, text, buttons=buttons, rev=rev)
    try:
        await event.answer()
    except Exception:
        pass


async def handle_menu_settings(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    sender_id = token.payload.get("sender_id")
    text, buttons = build_settings_menu(sender_id)
    await safe_edit(event, text, buttons=buttons, rev=rev)
    try:
        await event.answer()
    except Exception:
        pass


async def handle_setting_toggle(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    key = token.payload.get("key")
    current = bool(token.payload.get("current", False))
    sender_id = token.payload.get("sender_id")

    # Freshness check: verify against live DB state before mutating
    if key == "bot_antif":
        real_current = bool(gvarstatus("bot_antif") is not None)
    elif key == "pmpermit":
        real_current = bool(gvarstatus("pmpermit") is not None)
    elif key in {"ALLOW_NSFW", "SPOILER_MEDIA"}:
        raw = gvarstatus(key)
        real_current = bool(raw and str(raw).lower() in {"true", "yes", "1"})
    else:
        real_current = None

    if real_current is not None and real_current != current:
        # DB already updated; synchronize menu without repeat mutation
        text, buttons = build_settings_menu(sender_id)
        await safe_edit(event, text, buttons=buttons, rev=rev)
        try:
            await event.answer("⚠️ Setting was already updated. Menu synchronized.", alert=True)
        except Exception:
            pass
        return

    if key == "bot_antif":
        if current:
            delgvar("bot_antif")
            feedback = "Disabled Assistant Anti-Flood"
        else:
            addgvar("bot_antif", "true")
            feedback = "Enabled Assistant Anti-Flood"
    elif key == "pmpermit":
        if current:
            delgvar("pmpermit")
            feedback = "Disabled PM Guard (PMPERMIT)"
        else:
            addgvar("pmpermit", "true")
            feedback = "Enabled PM Guard (PMPERMIT)"
    elif key in {"ALLOW_NSFW", "SPOILER_MEDIA"}:
        new_val = not current
        if new_val:
            addgvar(key, "True")
            feedback = f"Set {key} to True"
        else:
            delgvar(key)
            feedback = f"Set {key} to False"
    else:
        feedback = "Unknown setting"

    text, buttons = build_settings_menu(sender_id)
    await safe_edit(event, text, buttons=buttons, rev=rev)
    try:
        await event.answer(f"✅ {feedback}", alert=False)
    except Exception:
        pass


async def handle_setting_cycle_rows(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    sender_id = token.payload.get("sender_id")
    current = int(token.payload.get("current", 5))

    try:
        real_current = int(gvarstatus("NO_OF_ROWS_IN_HELP") or 5)
    except (ValueError, TypeError):
        real_current = 5

    if real_current != current:
        # Stale state; resync
        text, buttons = build_settings_menu(sender_id)
        await safe_edit(event, text, buttons=buttons, rev=rev)
        try:
            await event.answer("⚠️ Pagination density already changed. Menu synchronized.", alert=True)
        except Exception:
            pass
        return

    # Cycle 5 -> 7 -> 10 -> 5
    cycle_map = {5: 7, 7: 10, 10: 5}
    new_rows = cycle_map.get(current, 5)
    addgvar("NO_OF_ROWS_IN_HELP", str(new_rows))

    text, buttons = build_settings_menu(sender_id)
    await safe_edit(event, text, buttons=buttons, rev=rev)
    try:
        await event.answer(f"✅ Pagination density set to {new_rows} rows", alert=False)
    except Exception:
        pass


async def handle_menu_tasks(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    sender_id = token.payload.get("sender_id")
    text, buttons = build_tasks_menu(sender_id)
    await safe_edit(event, text, buttons=buttons, rev=rev)
    try:
        await event.answer()
    except Exception:
        pass


async def handle_task_prompt_cancel(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    sender_id = token.payload.get("sender_id")
    text, buttons = build_task_cancel_confirmation_menu(token.payload, sender_id)
    await safe_edit(event, text, buttons=buttons, rev=rev)
    try:
        await event.answer()
    except Exception:
        pass


async def handle_task_confirm_cancel(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    source = token.payload.get("source", "tm")
    target_id = token.payload.get("target_id")
    name = token.payload.get("name", "")
    sender_id = token.payload.get("sender_id")

    type_label = f"AsyncTask #{target_id}" if source == "tm" else f"Job {target_id}"

    # Check if task is already completed before cancelling
    already_done = False
    if source == "tm" and target_id is not None:
        t_obj = task_manager.get_task(int(target_id))
        if t_obj is None or t_obj.is_done:
            already_done = True
    elif source == "js" and target_id:
        j_obj = job_supervisor.get_job(str(target_id))
        if j_obj is None or j_obj.status in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}:
            already_done = True

    if already_done:
        toast = f"ℹ️ {type_label} already finished or is no longer running."
    else:
        success = False
        if source == "tm" and target_id is not None:
            success = task_manager.cancel_task(int(target_id))
        elif source == "js" and target_id:
            success = await job_supervisor.cancel_job(str(target_id))

        if success:
            toast = f"🛑 Cancellation requested for {type_label} ({name})."
        else:
            toast = f"⚠️ {type_label} could not be stopped."

    text, buttons = build_tasks_menu(sender_id)
    await safe_edit(event, text, buttons=buttons, rev=rev)
    try:
        await event.answer(toast, alert=True)
    except Exception:
        pass


async def handle_menu_sysinfo(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    sender_id = token.payload.get("sender_id")
    text, buttons = build_sysinfo_menu(sender_id)
    await safe_edit(event, text, buttons=buttons, rev=rev)
    try:
        await event.answer()
    except Exception:
        pass


async def handle_menu_close(event: Any, token: CallbackToken) -> None:
    rev = await acquire_message_revision(event)
    sender_id = token.payload.get("sender_id")
    t_open = create_menu_token("menu_home", {"sender_id": sender_id}, sender_id)
    buttons = [[Button.inline("Open Menu", data=t_open)]]
    await safe_edit(event, "◈ Aetheris Control Menu Closed.", buttons=buttons, rev=rev)
    try:
        await event.answer("Menu closed", alert=False)
    except Exception:
        pass


async def handle_noop(event: Any, token: CallbackToken) -> None:
    try:
        await event.answer()
    except Exception:
        pass


def register_inline_menu_handlers(mgr=None) -> None:
    """Bind all menu handlers to the SecureCallbackManager instance."""
    manager = mgr or secure_callbacks
    manager.register_handler("menu_home", handle_menu_home)
    manager.register_handler("menu_categories", handle_menu_categories)
    manager.register_handler("menu_category", handle_menu_category)
    manager.register_handler("menu_plugin", handle_menu_plugin)
    manager.register_handler("menu_command", handle_menu_command)
    manager.register_handler("menu_settings", handle_menu_settings)
    manager.register_handler("setting_toggle", handle_setting_toggle)
    manager.register_handler("setting_cycle_rows", handle_setting_cycle_rows)
    manager.register_handler("menu_tasks", handle_menu_tasks)
    manager.register_handler("task_prompt_cancel", handle_task_prompt_cancel)
    manager.register_handler("task_confirm_cancel", handle_task_confirm_cancel)
    manager.register_handler("menu_sysinfo", handle_menu_sysinfo)
    manager.register_handler("menu_close", handle_menu_close)
    manager.register_handler("noop", handle_noop)


# Auto-register handlers on module load
register_inline_menu_handlers(secure_callbacks)
